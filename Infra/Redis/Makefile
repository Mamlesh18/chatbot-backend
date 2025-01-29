build:
	docker build -f ./Dockerfile -t mamlesh/chatterpy-redis:latest .
	
run:
	docker run -p 6379:6379  mamlesh/chatterpy-redis:latest

remove:
	docker rm -f chatterpy-redis || true

all:
	make build
	make remove
	make run