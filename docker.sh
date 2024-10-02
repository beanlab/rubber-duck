#!/bin/bash

CONTAINER_NAME="ducky_$(openssl rand -hex 4)"

docker build -t wjw37/byu-bean-lab-rubber-duck:latest .

docker run --name $CONTAINER_NAME -d wjw37/byu-bean-lab-rubber-duck:latest

