deploy:
	docker build -f ./Dockerfile -t mamlesh/chatterpy-prometheus:latest .
	
run:
	docker run -p 9090:9090 mamlesh/chatterpy-prometheus:latest

remove:
	docker rm -f chatterpy-prometheus || true

all:
	make deploy
	make remove
	make run