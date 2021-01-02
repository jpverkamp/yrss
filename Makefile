debug:
	docker build -t yrss2 .
	docker run -it -p 80:5000 -v $(shell pwd)/yrss2.db:/app/yrss2.db --env-file env.conf -e YRSS_DEBUG=true yrss2