deploy:
	docker build -t mamlesh/chatterpy-knwoldegebase:latest .
	docker run -d -p 5000:5000 --name chatterpy-knwoldegebase mamlesh/chatterpy-knwoldegebase:latest
run:
	docker run -d -p 5001:5001 --name chatterpy-knwoldegebase mamlesh/chatterpy-knwoldegebase:latest

remove:
	docker rm chatterpy-knwoldegebase
	