import os
import requests
from flask import Flask, request, Response
from prometheus_flask_exporter import PrometheusMetrics
from flasgger import Swagger
from libversion import version_util

app = Flask(__name__)
swagger = Swagger(app)
metrics = PrometheusMetrics(app)

# Fetch URL/port to model-service from environment variables (service name from docker-compose)
model_service_url = os.getenv('MODEL_SERVICE_URL', default='model-service')
model_service_port = os.getenv('MODEL_SERVICE_PORT', default='8081')


## Metrics

# General info
metrics.info('app_info', 'Application info', version=version_util.VersionUtil.get_version())

review_input_length = metrics.histogram(
	'input_length_vs_prediction', 'Histogram of review input lengths verus predictions',
	labels={'prediction': lambda response: response.text}
)

prediction_count_by_type = metrics.counter(
	'prediction_count_by_type', 'Number of predictions by type',
	labels={'prediction': lambda response: response.text}
)

active_prediction_requests = metrics.gauge(
	'active_prediction_requests', 'Number of requests being processed at a time'
)

#user satisfaction
happy_users_counter = metrics.counter(
	'happy_users', 'Number of happy users'
)
sad_users_counter = metrics.counter(
	'unsatisfied_users', 'Number of unsatisfied users'
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
	# Keep track of currently active requests
	# active_prediction_requests.inc()

	try:
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
			# prediction_count_by_type.inc()

			return model_service_response.text

		return 'Could not fetch prediction', 500
	finally:
		# Request was finished; decrease number of active requests
		# active_prediction_requests.dec()
		pass


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
		return version_util.VersionUtil.get_version()
	except Exception as e:
		print(e)
		return "Version not found", 500

@app.route('/update-feedback', methods=['GET'])
def update_feedback():
	"""
	Upon clicking the yes/no button, the yes and no counter
	should update to reflect user experience
	---
	parameters:
	  - name: input
	    in: body
	    description: JSON with 'satisfied' key and true or false as value.
	    required: true
	responses:
		200:
			description: Sent satisfaction (True="happy" or False="unhappy").
		400:
			description: Input is not a JSON object with "satisfied" as key.
		500:
			bad request
	"""
	try:
		msg = request.get_json()
	except Exception:
		return 'Payload is not a JSON object with "satisfied" as key.', 400

	if not 'satisfied' in msg:
		return 'JSON payload should contain "satisfied" key', 400

	feedback = msg['satisfied']
	if feedback:
		happy_users_counter.inc()
	elif not feedback:
		sad_users_counter.inc()

	return 'feedback succesfully processed'


app.run(host="0.0.0.0", port=5000)
