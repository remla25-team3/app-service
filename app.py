import os
import time
import json
import requests
from flask import Flask, request, jsonify, make_response
from prometheus_flask_exporter import PrometheusMetrics
from flasgger import Swagger, swag_from
from libversion import version_util
from flask_cors import CORS
from prometheus_client import Gauge

# Application setup
app = Flask(__name__)
CORS(app)

# Environment variables
model_service_host = os.getenv('MODEL_SERVICE_URL', 'model-service')
model_service_port = int(os.getenv('MODEL_SERVICE_PORT', 5000))
MODEL_SERVICE_URL = f"http://{model_service_host}:{model_service_port}"


# Helper function to get the sentiment from the model-service's JSON response
def get_sentiment_from_response(response):
    try:
        # The response from model-service is JSON
        return response.json.get("sentiment", "unknown")
    except (ValueError, AttributeError):
        # In case of non-JSON response or other errors
        return "error"
    
def get_current_app_version():
    """Reads the app version from the .release-please-manifest.json file."""
    try:
        with open('.release-please-manifest.json', 'r') as f:
            manifest = json.load(f)
            # The version is stored with the key "."
            return manifest.get('.', 'unknown')
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        #file is missing, not valid JSON, or the key is absent
        return "unknown"
    
# Metrics Configuration
metrics = PrometheusMetrics(app)
metrics.info('app_info', 'Application info', version=version_util.VersionUtil.get_version())

# Usability Histogram: Distribution of review lengths
review_length_histogram = metrics.histogram(
    'review_length_characters', 'Distribution of the number of characters in reviews',
    labels={'sentiment': lambda r: get_sentiment_from_response(r)}
)
# Usability Counter: User feedback on prediction accuracy
prediction_feedback_counter = metrics.counter(
    'prediction_feedback_total', 'Counts of user feedback on predictions',
    labels={'model_prediction': lambda: request.json.get('model_sentiment'),
            'user_feedback': lambda: request.json.get('user_sentiment')}
)
# Usability Gauge: Timestamp of the last user feedback
last_feedback_timestamp = Gauge(
    'last_feedback_timestamp_seconds', 'The timestamp of the last user feedback submission'
)

# Swagger API Documentation
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "App Service API",
        "description": "A service that acts as a proxy to the model-service for sentiment analysis of restaurant reviews.",
        "version": version_util.VersionUtil.get_version()
    }
}
swagger = Swagger(app, template=swagger_template)


# API Endpoints
@app.route('/predict', methods=['POST'])
@review_length_histogram 
@swag_from({
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'id': 'review_input',
                'type': 'object',
                'properties': {
                    'review': {
                        'type': 'string',
                        'example': 'This place is amazing!'
                    }
                },
                'required': ['review']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Prediction result from the model-service.',
            'schema': {
                'type': 'object',
                'properties': {
                    'sentiment': {'type': 'string'},
                    'confidence_score': {'type': 'number'},
                    'review': {'type': 'string'}
                }
            }
        },
        400: {'description': 'Invalid input, "review" key is missing.'},
        500: {'description': 'Error connecting to the model service or internal error.'}
    }
})
def predict():
    """
    Fetches the predicted sentiment of a restaurant review from `model-service`.
    """
    try:
        json_data = request.get_json()
        if not json_data or 'review' not in json_data:
            return jsonify({"error": "The 'review' key is missing from the request body."}), 400

        response = requests.post(f"{MODEL_SERVICE_URL}/predict", json=json_data, timeout=5)
        response.raise_for_status()

        flask_response = make_response(jsonify(response.json()), response.status_code)

        return flask_response
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Could not connect to model-service: {e}"}), 500


@app.route('/update-prediction', methods=['POST'])
@prediction_feedback_counter
@swag_from({
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'id': 'update_input',
                'type': 'object',
                'properties': {
                    'review': {
                        'type': 'string',
                        'example': 'The food was delicious!'
                    },
                    'sentiment': {
                        'type': 'string',
                        'example': 'positive'
                    }
                },
                'required': ['review', 'sentiment']
            }
        }
    ],
    'responses': {
        202: {'description': 'Feedback accepted and queued for processing.'},
        400: {'description': 'Invalid input.'}
    }
})
def update_prediction():
    """
    Receives user feedback to correct a prediction and updates metrics
    """
    last_feedback_timestamp.set_to_current_time()
    return jsonify({"status": f"Feedback received. Thanks!"}), 202

@app.route("/version", methods=["GET"])
@swag_from({
    'summary': 'Get all component versions',
    'description': 'Returns the versions of the app-service, its core lib-version dependency, and the connected model-service.',
    'responses': {
        200: {
            'description': 'A JSON object containing all component versions.',
            'schema': {
                'type': 'object',
                'properties': {
                    'app_service_version': {
                        'type': 'string',
                        'example': '1.2.0'
                    },
                    'lib_version': {
                        'type': 'string',
                        'example': '0.1.0'
                    },
                    'model_service_version': {
                        'type': 'string',
                        'example': '0.2.0'
                    }
                }
            }
        }
    }
})
def get_versions():
    """
    Gets the versions of this app-service, its lib-version dependency,
    and the connected model-service.
    """
    app_version = get_current_app_version()
    library_version = version_util.VersionUtil.get_version()
    model_version = "unknown"

    try:
        response = requests.get(f"{MODEL_SERVICE_URL}/version", timeout=3)
        response.raise_for_status()
        model_version = response.json().get('version', 'unknown')
    except requests.exceptions.RequestException:
        model_version = "not reachable"
    except Exception:
        model_version = "error reading version"

    response_data = {
        "app_service_version": app_version,
        "lib_version": library_version,
        "model_service_version": model_version
    }
    
    return jsonify(response_data), 200

# This check is important for running the app with 'flask run'
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)