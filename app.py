import os
import requests
from flask import Flask, request, Response
from prometheus_flask_exporter import PrometheusMetrics
from flasgger import Swagger
from libversion.version_util import VersionUtil

app = Flask(__name__)
swagger = Swagger(app)
metrics = PrometheusMetrics(app)

# Fetch URL/port to model-service from environment variables (service name from docker-compose)
model_service_url = os.getenv('MODEL_SERVICE_URL', default='model-service')
model_service_port = os.getenv('MODEL_SERVICE_PORT', default='8081')


## Metrics

# General info
metrics.info('app_info', 'Application info', version=VersionUtil.get_version())

review_input_length = metrics.histogram(
	'input_length_vs_prediction', 'Histogram of review input lengths verus predictions',
	labels={'prediction': lambda response: response.text}
)

prediction_count_by_type = metrics.counter(
	'prediction_count_by_type', 'Number of predictions by type',
	labels={'prediction': lambda response: response.text}
)


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
		# If we got a response from `model-service`, feed the input's length to the metrics
		review_input_length.observe(len(msg['review']))

		# Also increment prediction count by type
		prediction_count_by_type.inc()

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


app.run(host="0.0.0.0", port=5000)
