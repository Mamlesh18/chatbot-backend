deploy-run:
	docker build -f ./Dockerfile -t mamlesh/knowledgebase:latest .
	docker rm -f knowledgebase-container || true
	docker run -p 8080:8080 --name knowledgebase-container mamlesh/knowledgebase:latest
