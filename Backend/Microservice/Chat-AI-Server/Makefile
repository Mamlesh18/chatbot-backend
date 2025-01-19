deploy:
	docker build -f ./Dockerfile -t mamlesh/chatterpy-auth:latest .
	
run:
	docker run -p 5000:5000 --network my_network mamlesh/chatterpy-auth:latest

remove:
	docker rm -f chatterpy-auth || true

all:
	make deploy
	make remove
	make run