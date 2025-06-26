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

def get_frontend_version(default='unknown'):
    """Gets the frontend version from the 'X-App-Frontend-Version' header."""
    return request.headers.get('X-App-Frontend-Version', default)

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
    labels={'sentiment': lambda r: get_sentiment_from_response(r),
            'frontend_version': lambda: get_frontend_version()}
)
# Usability Counter: User feedback on prediction accuracy
prediction_feedback_counter = metrics.counter(
    'prediction_feedback_total', 'Counts of user feedback on predictions',
    labels={'model_prediction': lambda: request.json.get('model_sentiment'),
            'user_feedback': lambda: request.json.get('user_sentiment'),
            'frontend_version': lambda: get_frontend_version()}
)
# Usability Gauge: Timestamp of the last user feedback
last_feedback_timestamp = Gauge(
    'last_feedback_timestamp_seconds', 'The timestamp of the last user feedback submission',
    ['frontend_version']
)

# Business Counter: Number of predictions made
predictions_made_total = metrics.counter(
    'predictions_made_total', 'Total number of prediction requests made',
    labels={'frontend_version': lambda: get_frontend_version()}
)

# Swagger API Documentation
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title":       "App Service: REMLA Team 3",
        "description": "App Service APIs",
        "version":     version_util.VersionUtil.get_version()
    },
    "basePath": "/api",
}
swagger_config = {
    "headers": [],
    "specs_route": "/app/apidocs",            # was "/apidocs"
    "specs": [
        {
            "endpoint": "apispec_1",
            "route":    "/app/apispec_1.json",  # was "/apispec_1.json"
            "rule_filter":  lambda rule: True,
            "model_filter": lambda tag:  True
        }
    ],
    "static_url_path": "/app/flasgger_static"  # was "/flasgger_static"
}

swagger = Swagger(app,
                  template=swagger_template,
                  config=swagger_config)
# swagger = Swagger(app, template=swagger_template)


# API Endpoints
@app.route('/predict', methods=['POST'])
@review_length_histogram 
@predictions_made_total
@swag_from({
    'summary': 'Forward review for sentiment prediction',
    'description': 'Accepts review text, calls model-service /predict, and returns its response.',
    'tags': ['Prediction'],
    'parameters': [
        {
            'in': 'body', 'name': 'body', 'required': True,
            'schema': {
                'type': 'object', 'required': ['review'],
                'properties': {
                    'review': { 'type': 'string', 'example': 'Great food!' }
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Model-service prediction result.',
            'schema': {
                'type': 'object',
                'properties': {
                    'sentiment': {'type': 'string'},
                    'confidence_score': {'type': 'number'},
                    'review': {'type': 'string'}
                }
            }
        },
        400: {'description': 'Missing review key.'},
        500: {'description': 'Connection or internal error.'}
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
    'summary': 'Submit feedback on prediction',
    'description': 'Accepts user-corrected sentiment feedback for a review.',
    'tags': ['Feedback'],
    'parameters': [
        {
            'in': 'body', 'name': 'body', 'required': True,
            'schema': {
                'type': 'object', 'required': ['review', 'sentiment'],
                'properties': {
                    'review': { 'type': 'string', 'example': 'Great food!' },
                    'sentiment': { 'type': 'string', 'example': 'positive' }
                }
            }
        }
    ],
    'responses': {
        202: {'description': 'Feedback accepted.'},
        400: {'description': 'Invalid input.'}
    }
})
def update_prediction():
    """
    Receives user feedback to correct a prediction and updates metrics
    """
    frontend_version = get_frontend_version()
    last_feedback_timestamp.labels(frontend_version=frontend_version).set_to_current_time()
    return jsonify({"status": f"Feedback received. Thanks!"}), 202

@app.route("/version", methods=["GET"])
@swag_from({
    'summary': 'Get component versions',
    'description': 'Returns versions of the app-service, lib-version, and model-service.',
    'tags': ['Monitoring'],
    'responses': {
        200: {
            'description': 'Version details.',
            'schema': {
                'type': 'object',
                'properties': {
                    'app_service_version': {'type': 'string'},
                    'lib_version': {'type': 'string'},
                    'model_service_version': {'type': 'string'}
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