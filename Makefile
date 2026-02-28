SHELL := /bin/sh

PROJECT_ID ?= sylvain-488510
REGION ?= us-central1
AR_REPO ?= quantum
IMAGE_NAME ?= quantum-ml
IMAGE_TAG ?= latest
TF_DIR ?= infra

IMAGE_URI := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(AR_REPO)/$(IMAGE_NAME):$(IMAGE_TAG)

.PHONY: help check-project auth-docker docker-build docker-push tf-init tf-plan tf-apply deploy-all

help:
	@echo "Targets:"
	@echo "  make docker-build PROJECT_ID=<id> [REGION=us-central1 AR_REPO=quantum IMAGE_NAME=quantum-ml IMAGE_TAG=latest]"
	@echo "  make docker-push PROJECT_ID=<id> [...]"
	@echo "  make tf-init"
	@echo "  make tf-plan"
	@echo "  make tf-apply"
	@echo "  make deploy-all PROJECT_ID=<id>  # build + push + terraform apply"
	@echo ""
	@echo "Resolved image URI:"
	@echo "  $(IMAGE_URI)"

check-project:
	@if [ -z "$(PROJECT_ID)" ]; then \
		echo "PROJECT_ID is required. Example: make deploy-all PROJECT_ID=my-gcp-project"; \
		exit 1; \
	fi

auth-docker: check-project
	gcloud auth configure-docker $(REGION)-docker.pkg.dev -q

docker-build: check-project
	docker build -t $(IMAGE_URI) -f Dockerfile.ml-job .
	@echo "Built: $(IMAGE_URI)"

docker-push: check-project
	docker push $(IMAGE_URI)
	@echo "Pushed: $(IMAGE_URI)"

tf-init:
	terraform -chdir=$(TF_DIR) init

tf-plan:
	terraform -chdir=$(TF_DIR) plan

tf-apply:
	terraform -chdir=$(TF_DIR) apply

deploy-all: auth-docker docker-build docker-push tf-init tf-apply
	@echo "Deployment complete."
	@echo "Ensure $(TF_DIR)/terraform.tfvars has container_image=$(IMAGE_URI)"
