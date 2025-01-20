build:
	docker build -f ./Dockerfile -t mamlesh/chatterpy-lawai:latest .
	
run:
	docker run -p 5000:5000  mamlesh/chatterpy-lawai:latest

remove:
	docker rm -f chatterpy-lawai || true

all:
	make build
	make remove
	make run