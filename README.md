# app-service

`app-service` serves as the application back-end API.

## Features

- [x] Fetches restaurant review sentiment predictions from `model-service` through REST requests
  - [ ] `model-service` domain name is passed as an environment variable
- [ ] Provides an endpoint to have `model-service` update or confirm its prediction of a restaurant review's sentiment (_TODO: needs to be actually implemented, but endpoint exists_)
- [x] Integrates `lib-version` to display the latest version
- [x] Automatic versioning based on Git version tag
- [x] Automatic artifact release through a GitHub Actions workflow

## API usage

`api-service` exposes a REST API on port 8080 (_todo: configure `model-service` DNS name in ENV variable_).
The following endpoints are available:

### `POST`

- `http://[domain]:[port]/get-prediction`

  - Fetches a restaurant review sentiment prediction from `model-service`. 
  - Payload: `{"review": "some user review"}`
  - Returns: `"positive"` or `"negative"` classification

- `http://[domain]:[port]/update-prediction`

  - Requests `model-service` to update or confirm a restaurant review sentiment prediction.
  - Payload: `{"review": "some user review", "label": "[positive]/[negative]"}`
  - Returns: `OK` if `model-service` could update its prediction

### `GET`

- `http://[domain]:[port]/version`
  
  - Returns: latest version from `lib-version`
