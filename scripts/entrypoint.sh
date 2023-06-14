#!/bin/bash

set -e
echo "Starting"

case "$1" in
  api)

	gunicorn --chdir app --timeout 300 "app:create_app()" -b "0.0.0.0:5001" -k gevent -w 5
	;;
esac