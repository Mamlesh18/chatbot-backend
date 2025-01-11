deploy:
	docker build -f ./Dockerfile -t mamlesh/chatterpy-auth:latest .
	docker rm -f chatterpy-auth || true
	docker run -p 5000:5000 --name chatterpy-auth mamlesh/chatterpy-auth:latest
