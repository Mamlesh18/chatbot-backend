build:
	docker build -f ./Dockerfile -t mamlesh/chatterpy-restai:latest .
	
run:
	docker run -p 5000:5000  mamlesh/chatterpy-restai:latest

remove:
	docker rm -f chatterpy-restai || true

all:
	make build
	make remove
	make run