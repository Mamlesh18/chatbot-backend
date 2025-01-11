deploy-run:
	docker build -f ./Dockerfile -t mamlesh/chatterpy-krakend:latest .
	docker rm -f knowledgebase-container || true
	docker run -p 8080:8080 --name chatterpy-krakend mamlesh/chatterpy-krakend:latest
