import os
import requests
from flask import Flask, request, Response
from flasgger import Swagger
from libversion.version_util import VersionUtil

app = Flask(__name__)
swagger = Swagger(app)

# Fetch URL/port to model-service from environment variables (service name from docker-compose)
model_service_url = os.getenv('MODEL_SERVICE_URL', default='model-service')
model_service_port = os.getenv('MODEL_SERVICE_PORT', default='8081')


## Metrics
num_predictions_fetched = 0		# Total number of predictions fetched by user
times_prediction_updated = 0	# Number of times the user updated a prediction


@app.route('/get-prediction', methods=['POST'])
def get_prediction():
	"""
	Fetches the predicted sentiment of a restaurant review from `model-service`.
	---
	parameters:
	  - name: input
	    in: body
	    description: JSON with 'review' key and the user review as value.
	    required: true
	responses:
		200:
			description: Prediction result ("positive" or "negative").
		400:
			description: Input is not a JSON object with "review" as key.
		500:
			description: Prediction could not be fetched from `model-service`.
	"""
	try:
		msg = request.get_json()
	except Exception:
		return 'Payload should be a JSON object with "review" as key', 400

	if not 'review' in msg:
		return 'JSON payload should contain "review" key', 400

	req_url = f'http://{model_service_url}:{model_service_port}/predict'
	try:
		model_service_response = requests.post(req_url, json=msg)
	except Exception:
		return f'Could not connect to model-service', 500

	if model_service_response.ok:
		return model_service_response.text

	return 'Could not fetch prediction', 500


@app.route('/update-prediction', methods=['POST'])
def update_prediction():
	"""
	Updates or confirms a prediction.
	This request is forwarded to `model-service` for processing.
	---
	parameters:
	  - name: input
	    in: body
	    description: JSON with "review" and "label" keys.
	    required: true
	responses:
		200:
			description: Request was OK.
		400:
			description: Input is not in a correct format.
		500:
			description: Could not connect to `model-service`.
	"""
	try:
		msg = request.get_json()
	except Exception:
		return 'Payload should be a JSON object with "review" and "label" as keys', 400

	if not 'review' in msg:
		return 'JSON payload should contain "review" key', 400
	if not 'label' in msg:
		return 'JSON payload should contain "label" key', 400

	return f'Review label was successfully updated to {msg['label']}'


@app.route("/version", methods=["GET"])
def get_lib_version():
	"""
	Gets the version from the lib-version package.
	---
	responses:
		200:
			description: Version (v#.#.#) from lib-version.
		500:
			description: Version could not be retrieved.
	"""
	try:
		return VersionUtil.get_version()
	except Exception as e:
		print(e)
		return "Version not found", 500


@app.route("/metrics", methods=["GET"])
def metrics():
	"""
	Endpoint for metrics inspectable in Prometheus.
	---
	responses:
		200:
			description: >
				Plain text in Prometheus-friendly format.
				Metrics: num_predictions_fetched (counter), times_prediction_updated (counter).
	"""
	global num_predictions_fetched, times_prediction_updated

	m  = '# HELP num_predictions_fetched Number of predictions fetched from `model-service`.\n'
	m += '# TYPE num_predictions_fetched counter\n'
	m += f'num_predictions_fetched = {str(num_predictions_fetched)}\n\n'

	m += '# HELP times_prediction_updated Number of times the user updated a prediction from `model-service`.\n'
	m += '# TYPE times_prediction_updated counter\n'
	m += f'times_prediction_updated = {str(times_prediction_updated)}\n\n'

	return Response(m, mimetype='text/plain')

app.run(host="0.0.0.0", port=5000)
