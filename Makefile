SHELL = /bin/sh

$(eval BACKEND_NAME=dod_surveystream_backend)
$(eval BACKEND_PORT=5001)
$(eval FRONTEND_NAME=dod_surveystream_frontend)
$(eval VERSION=0.1)
$(eval TEST_RUNNER_NAME=surveystream_test_runner)
$(eval PROD_NEW_ACCOUNT=923242859002)
$(eval STAGING_ACCOUNT=210688620213)
$(eval ADMIN_ACCOUNT=077878936716)
$(eval DEV_ACCOUNT=453207568606)


login:
	@aws sso login --profile surveystream_dev

image:
	@docker build -f Dockerfile.api --rm --build-arg NAME=$(BACKEND_NAME) --build-arg PORT=$(BACKEND_PORT) --platform=linux/amd64 -t $(BACKEND_NAME):$(VERSION) .

db-tunnel:
	# Open a connection to the remote db via the bastion host
	@aws ssm start-session \
	--target i-0c08ac05a9796bc30 \
	--profile surveystream_dev \
	--region ap-south-1 \
	--document-name AWS-StartPortForwardingSession \
	--parameters '{"portNumber":["5432"],"localPortNumber":["5432"]}'

container-up:
	# Start a local version of the web app that uses the DoD dev database
	@BACKEND_NAME=${BACKEND_NAME} \
	BACKEND_PORT=${BACKEND_PORT} \
	VERSION=${VERSION} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.remote-dev-db.yml -f docker-compose/docker-compose.override.yml up -d

container-down:
	@BACKEND_NAME=${BACKEND_NAME} \
	BACKEND_PORT=${BACKEND_PORT} \
	VERSION=${VERSION} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.remote-dev-db.yml -f docker-compose/docker-compose.override.yml down

image-stg:
	@docker build -f Dockerfile.api --rm --build-arg NAME=$(BACKEND_NAME) --build-arg PORT=$(BACKEND_PORT) --platform=linux/amd64 -t $(BACKEND_NAME):$(VERSION) . 
	@docker tag $(BACKEND_NAME):$(VERSION) $(STAGING_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com/web-callisto-ecr-repository:backend
	@aws ecr get-login-password \
    --region ap-south-1 \
	--profile surveystream_staging | \
	docker login \
    --username AWS \
    --password-stdin $(STAGING_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com
	@docker push $(STAGING_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com/web-callisto-ecr-repository:backend


container-up-stg:
	# Configure ecs-cli options
	@ecs-cli configure --cluster web-callisto-cluster \
	--default-launch-type EC2 \
	--region ap-south-1 \
	--config-name dod-surveystream-web-app-backend-config

	@STAGING_ACCOUNT=${STAGING_ACCOUNT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	ecs-cli compose -f docker-compose/docker-compose.stg.yml \
	--aws-profile surveystream_staging \
	--project-name api \
	--cluster-config dod-surveystream-web-app-backend-config \
	--task-role-arn arn:aws:iam::$(STAGING_ACCOUNT):role/web-callisto-task-role \
	service up \
	--create-log-groups \
	--deployment-min-healthy-percent 0

container-down-stg:
	@ecs-cli compose -f docker-compose/docker-compose.stg.yml \
	--aws-profile surveystream_staging \
	--region ap-south-1 \
	--project-name api \
	--cluster-config dod-surveystream-web-app-backend-config \
	--cluster web-callisto-cluster \
	service down --timeout 10

image-prod-new:
	@docker build -f Dockerfile.api --rm --build-arg NAME=$(BACKEND_NAME) --build-arg PORT=$(BACKEND_PORT) --platform=linux/amd64 -t $(BACKEND_NAME):$(VERSION) . 
	@docker tag $(BACKEND_NAME):$(VERSION) $(PROD_NEW_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com/web-ecr-repository:backend
	@aws ecr get-login-password \
    --region ap-south-1 \
	--profile surveystream_prod | \
	docker login \
    --username AWS \
    --password-stdin $(PROD_NEW_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com
	@docker push $(PROD_NEW_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com/web-ecr-repository:backend

	@docker build -f Dockerfile.client --rm --platform=linux/amd64 -t $(FRONTEND_NAME):$(VERSION) . 
	@docker tag $(FRONTEND_NAME):$(VERSION) $(PROD_NEW_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com/web-ecr-repository:frontend
	@aws ecr get-login-password \
    --region ap-south-1 \
	--profile surveystream_prod | \
	docker login \
    --username AWS \
    --password-stdin $(PROD_NEW_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com
	@docker push $(PROD_NEW_ACCOUNT).dkr.ecr.ap-south-1.amazonaws.com/web-ecr-repository:frontend

container-prod-new:
	# Configure ecs-cli options
	@ecs-cli configure --cluster web-cluster \
	--default-launch-type EC2 \
	--region ap-south-1 \
	--config-name dod-surveystream-web-app-config

	@PROD_NEW_ACCOUNT=${PROD_NEW_ACCOUNT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	ecs-cli compose -f docker-compose/docker-compose.prod-new.yml \
	--aws-profile surveystream_prod \
	--project-name dod-surveystream-web-app \
	--cluster-config dod-surveystream-web-app-config \
	--task-role-arn arn:aws:iam::$(PROD_NEW_ACCOUNT):role/web-task-role \
	service up \
	--target-group-arn arn:aws:elasticloadbalancing:ap-south-1:$(PROD_NEW_ACCOUNT):targetgroup/surveystream-lb-tg-443/13b8531a30c92246 \
	--container-name client \
	--container-port 80 \
	--create-log-groups \
	--deployment-min-healthy-percent 0

down-prod-new:
	@ecs-cli compose -f docker-compose/docker-compose.prod-new.yml \
	--aws-profile surveystream_prod \
	--region ap-south-1 \
	--project-name dod-surveystream-web-app \
	--cluster-config dod-surveystream-web-app-config \
	--cluster web-cluster \
	service down --timeout 10

image-prod:
	@docker build -f Dockerfile.api --rm --build-arg NAME=$(BACKEND_NAME) --build-arg PORT=$(BACKEND_PORT) -t $(BACKEND_NAME):$(VERSION) . 
	@docker tag $(BACKEND_NAME):$(VERSION) 678681925278.dkr.ecr.ap-south-1.amazonaws.com/dod-surveystream-web-app:backend
	@$$(aws ecr get-login --no-include-email --region ap-south-1)
	@docker push 678681925278.dkr.ecr.ap-south-1.amazonaws.com/dod-surveystream-web-app:backend

	@docker build -f Dockerfile.client --rm -t $(FRONTEND_NAME):$(VERSION) . 
	@docker tag $(FRONTEND_NAME):$(VERSION) 678681925278.dkr.ecr.ap-south-1.amazonaws.com/dod-surveystream-web-app:frontend
	@$$(aws ecr get-login --no-include-email --region ap-south-1)
	@docker push 678681925278.dkr.ecr.ap-south-1.amazonaws.com/dod-surveystream-web-app:frontend

container-up-prod:
	# Configure ecs-cli options
	@ecs-cli configure --cluster dod-surveystream-web-app-cluster \
	--default-launch-type EC2 \
	--region ap-south-1 \
	--config-name dod-surveystream-web-app-config

	@ecs-cli compose -f docker-compose/docker-compose.aws.yml \
	--project-name dod-surveystream-web-app \
	--cluster-config dod-surveystream-web-app-config \
	--task-role-arn arn:aws:iam::678681925278:role/dod-surveystream-web-app-task-role \
	service up \
	--target-group-arn arn:aws:elasticloadbalancing:ap-south-1:678681925278:targetgroup/dod-surveystream-web-app-tg-443/440079da841258e5 \
	--container-name client \
	--container-port 80 \
	--create-log-groups \
	--deployment-min-healthy-percent 0

container-down-prod:
	@ecs-cli compose -f docker-compose/docker-compose.aws.yml \
	--project-name dod-surveystream-web-app \
	--cluster-config dod-surveystream-web-app-config \
	service down

image-test-e2e:
	@docker build -f Dockerfile.test-runner --rm --build-arg NAME=$(TEST_RUNNER_NAME) -t $(TEST_RUNNER_NAME):$(VERSION) .

run-test-e2e:
	@TEST_RUNNER_NAME=${TEST_RUNNER_NAME} \
	BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.test-e2e.yml -f docker-compose/docker-compose.override-test-e2e.yml run --rm test ;
	
	@TEST_RUNNER_NAME=${TEST_RUNNER_NAME} \
	BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.test-e2e.yml -f docker-compose/docker-compose.override-test-e2e.yml rm -fsv