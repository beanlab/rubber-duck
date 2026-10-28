#!/bin/bash
set -e

echo "Logging in to ECR"
sudo aws ecr get-login-password --region us-west-2 | sudo docker login --username AWS --password-stdin 844825014198.dkr.ecr.us-west-2.amazonaws.com

BRANCH='master'
#SHA='608d0'
#SHA='f51ad'
#SHA='78004'
#SHA='7b347'
#SHA='fbafc'

#SHA='044d8'
#SHA='e34cf'  # config cs 111
#SHA='d8738'  # config cs 312
#SHA='a1c16'  # add stats scatter/regression
#SHA='7aa5b'  # new run_agent architecture
#SHA='91123'  # fix stats type bug
#SHA='cd1b9'  # speed up stats dialog
#SHA='eb792'  # fix registration bug
#SHA='4a8a7'  # logging in metadata load
#SHA='6dfbc'  # CS Facult Server
#SHA='c64db'  # registration name check, change, and logging fixes
#SHA='84758'  # more logging fixes
#SHA='7fb33'  # handle 'Resend' in registration workflow
#SHA='26fbc'  # update dependencies
#SHA='21382'  # registration fixes
#SHA='ae3c1'  # registration improvements; stats plot_density
#SHA='67160'  # user-led workflow for stats; density plot;
#SHA='6e077'  #  metadata for stats
#SHA='f7238' # fix user-led and metadata bugs
#SHA='4b3ef' # fix user-led convo timeout
#SHA='76449' # update quest 0.2.16
#SHA='bbaa4' # fix s3 metadata
#SHA='9f2fe' # fix metadata logging
#SHA='b2f52' # more metadata logging
#SHA='a26d9' # fix default metadata to have display_name
#SHA='b43b9' # add display_name to s3 default metadata
#SHA='e2220' # better handling of alternate encodings; remove unnecessary warnings in timeouts.
#SHA='d4bf5' # standard duck prompt - concludes convos better
#SHA='d2a53' # CS 312 duck pond and project review
#SHA='0c4af' # CS 312 project review - fix initial_instructions key
#SHA='9cab6' # CS 312 add rubrics
#SHA='1df2c' # Updates to CS 312 rubrics
#SHA='1d2e2' # Stats duck uses docker. Good luck.
#SHA='49724' # fix s3 dataset mounting
#SHA='61848' # fix write_file return
#SHA='0b46d' # general improvements to stats duck
#SHA='f338b' # fix registration workflow
#SHA='578e4' # stats updates and 301R registration
#SHA='11d48' # stats updates
#SHA='d1e47' # better markdown tables in stats
#SHA='1246a' # fix registration logging
#SHA='2c792' # fix 301R registration config
#SHA='385fc' # better stats; fix error reporting
#SHA='cfff2' # more stats improvments; metadata
#SHA='a8598' # better error formatting
#SHA='2d8dd' # stats prompt; error handling.
#SHA='7ece0' # feedback fix; report command help; config cleanup
#SHA='32bfb' # support for include in config
#SHA='2ea67' # fix config; improved registration; cs metrics
#SHA='5c990' # support config env var again
#SHA='d74ce' # fix missing channel_id in config
#SHA='ff421' # correct CS110 duckpond channel ID
#SHA='54cd8' # semantic caching for stats; moved to python 3.12 in the docker
#SHA='5cf1b' # bug fix in reporting; CS 110 review channel
#SHA='d6c4a' # cache handling; april 1st ;)
#SHA='a8df9' # stats prompt improvements
#SHA='c9a0a' # stats prompt improvements
#SHA='e1fb3' # stats prompt and error logging
#SHA='09564' # CS 111 channel
#SHA='a2293' # CS 110 debugging practice
#SHA='844ce' # CS 110 independent-study role for registration
#SHA='4ac59' # CS 110 debugging practice better
#SHA='f2da5' # Fix CS 110 registration duck config typo
#SHA='eaaa9' # Change handling of errors in response_complete.py
SHA='09e1a' # include latest stats dataset

TAG="$BRANCH-$SHA"

echo
echo "Pulling $TAG"
sudo docker pull 844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:$TAG

CONTAINER_NAME='duck'
#CONTAINER_NAME='debug-duck'

if [ "$(sudo docker ps -a -q -f name=$CONTAINER_NAME )" ]; then
    echo "Stopping existing container: $CONTAINER_NAME"
    sudo docker stop $CONTAINER_NAME
    sudo docker rm $CONTAINER_NAME
fi

echo
echo "Starting container from $TAG"
sudo docker run \
        -d --name $CONTAINER_NAME \
	--env-file /home/ubuntu/.env \
	-e CONFIG_FILE_S3_PATH=s3://rubber-duck-config/production-configs/production-config-$SHA.yaml \
	--mount type=bind,src='/home/ubuntu/rubber-duck.db',dst=/rubber-duck.db \
	-v /var/run/docker.sock:/var/run/docker.sock \
        844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:$TAG  \
	

	#-e CONFIG_FILE_S3_PATH=s3://rubber-duck-config/production-configs/production-config-3ab9d.yaml \

# Remove prior images so we don't run out of space on the disk
echo
echo "Cleaning up old images"
sudo docker image prune -af

echo
sudo docker ps

#sudo docker run \
#	-it --rm \
#	--env-file `readlink -f ~/.env` \
#        844825014198.dkr.ecr.us-west-2.amazonaws.com/beanlab/rubber-duck:$TAG bash
#	
