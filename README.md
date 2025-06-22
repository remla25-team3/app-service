# App Service

This repository contains the `app-service`, the central API gateway for the REMLA Restaurant Sentiment Analysis application. It acts as the primary backend for the `app-frontend` and is responsible for orchestrating requests, collecting usability metrics, and communicating with the internal `model-service`.

---

### 🏛️ Architecture & Communication

This service is the "brain" of the application's backend logic, sitting between the user-facing frontend and the specialized machine learning model service.

The typical workflow is:
1.  The `app-frontend` sends all user-driven API requests (for predictions, feedback, or version info) exclusively to this `app-service`.
2.  This service handles the request:
    * For predictions (`/predict`), it forwards the request to the `model-service` and returns the model's response to the frontend.
    * For user feedback (`/update-prediction`), it processes the data and updates key usability metrics.
    * For version info (`/version`), it gathers version data from itself, it's `lib-version` dependency, and the `model-service` to provide a consolidated view.
3.  It enables Cross-Origin Resource Sharing (CORS) so that the `app-frontend`, served from a different origin, can securely interact with its API.

---

### 🚀 Features

* **API Gateway**: Provides a stable and consistent API for the `app-frontend`, decoupling it from the internal backend architecture.
* **CORS Enabled**: Correctly configured to allow requests from the `app-frontend` client.
* **Rich Usability Monitoring**: Implements three key use-case-specific metrics to monitor user interaction and model performance:
    * `prediction_feedback_total` (**Counter**): Shows labeled counts of user feedback (e.g., `model_prediction="positive", user_feedback="negative"`). An increase in disagreements can signal model performance degradation.
    * `review_length_characters` (**Histogram**): Measures the distribution of review lengths to understand user engagement.
    * `last_feedback_timestamp_seconds` (**Gauge**): Records the timestamp of the last time a user provided feedback.
* **Version Aggregation**: The `/version` endpoint dynamically queries the `model-service` and combines its version with its own and `lib-version`'s, providing a complete system overview.
* **Interactive API Documentation**: Auto-generates an interactive Swagger UI documentation page at `/apidocs`.
* **Production-Ready**: Runs on a Gunicorn WSGI server, as defined in the `Dockerfile`.
* **Automated Releases**: New versions of the service are drafted automatically based on Conventional Commits.

---
