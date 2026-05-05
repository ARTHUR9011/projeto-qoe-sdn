.PHONY: controller topology permissions clean baseline

controller:
	./scripts/start_controller.sh

topology:
	./scripts/start_topology.sh

permissions:
	chmod +x scripts/*.sh

clean:
	./scripts/clean.sh

baseline:
	./scripts/run_baseline.sh
