SHELL = /bin/sh

$(eval BACKEND_NAME=surveystream_backend)
$(eval BACKEND_PORT=5001)
$(eval VERSION=0.1)
$(eval ADMIN_ACCOUNT=077878936716)
$(eval DEV_ACCOUNT=453207568606)


login:
	@export AWS_PROFILE=surveystream_dev
	@aws sso login --profile surveystream_dev

image:
	@docker build -f Dockerfile.api --rm --build-arg NAME=$(BACKEND_NAME) --build-arg PORT=$(BACKEND_PORT) --platform=linux/amd64 -t $(BACKEND_NAME):$(VERSION) .

data-db-tunnel:
	# Open a connection to the remote db via the bastion host
	@aws ssm start-session \
	--target i-0ddd10471f2a098be \
	--profile surveystream_dev \
	--region ap-south-1 \
	--document-name AWS-StartPortForwardingSession \
	--parameters '{"portNumber":["5432"],"localPortNumber":["5432"]}'

web-db-tunnel:
	# Open a connection to the remote db via the bastion host
	@aws ssm start-session \
	--target i-0ddd10471f2a098be \
	--profile surveystream_dev \
	--region ap-south-1 \
	--document-name AWS-StartPortForwardingSession \
	--parameters '{"portNumber":["5433"],"localPortNumber":["5432"]}'

container-up:
	# Start a local version of the web app that uses the remote dev database
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

run-unit-tests:
	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	USE_DB_MIGRATIONS=false \
	docker-compose -f docker-compose/docker-compose.unit-test.yml -f docker-compose/docker-compose.override-unit-test.yml run --rm api ;
	
	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.unit-test.yml -f docker-compose/docker-compose.override-unit-test.yml rm -fsv

profile-locations:
	mkdir -p profiling/outputs
	
	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.profiling.yml -f docker-compose/docker-compose.override-unit-test.yml run --rm api ;
	
	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.profiling.yml -f docker-compose/docker-compose.override-unit-test.yml rm -fsv

generate-db-migration-dev:
	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.db-migrate.yml -f docker-compose/docker-compose.override.yml run --rm api ;

	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.db-migrate.yml -f docker-compose/docker-compose.override.yml rm -fsv

apply-db-migration-dev:
	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.db-upgrade.yml -f docker-compose/docker-compose.override.yml run --rm api ;

	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.db-upgrade.yml -f docker-compose/docker-compose.override.yml rm -fsv

downgrade-db-dev:
	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.db-downgrade.yml -f docker-compose/docker-compose.override.yml run --rm api ;

	@BACKEND_NAME=${BACKEND_NAME} \
	VERSION=${VERSION} \
	BACKEND_PORT=${BACKEND_PORT} \
	ADMIN_ACCOUNT=${ADMIN_ACCOUNT} \
	docker-compose -f docker-compose/docker-compose.db-downgrade.yml -f docker-compose/docker-compose.override.yml rm -fsv

