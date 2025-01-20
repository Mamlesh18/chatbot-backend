deploy:
	docker build -t custom-grafana .
	docker rm -f grafana || true
	docker run -d --name grafana -p 8001:3000 -v grafana_data:/var/lib/grafana custom-grafana
run:
	docker run -d --name grafana -p 8001:8001 -v grafana_data:/var/lib/grafana custom-grafana