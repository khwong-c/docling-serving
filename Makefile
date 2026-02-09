all:
	docker build -t localhost:32000/docling-serving:deployment --target runtime-cu128 .

deploy: all
	docker push localhost:32000/docling-serving:deployment
	helm upgrade docling-serving deployment -f values.deployment.yaml || helm install docling-serving deployment -f values.deployment.yaml

destroy:
	helm uninstall docling-serving
