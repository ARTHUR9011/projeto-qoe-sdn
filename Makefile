.PHONY: controller controller-qoe topology topology-etapa3 permissions clean baseline demo demo-fast demo-full demo-presentation show-demo-results

controller:
	./scripts/start_controller.sh

controller-qoe:
	./scripts/start_controller.sh qoe

topology:
	./scripts/start_topology.sh

topology-etapa3:
	./scripts/start_topology.sh etapa3

permissions:
	chmod +x scripts/*.sh scripts/*.py

clean:
	./scripts/clean.sh

baseline:
	./scripts/run_baseline.sh

demo: permissions
	./scripts/demo_todas_etapas.sh --skip-stage3-sem-controle

demo-presentation: permissions
	./scripts/demo_todas_etapas.sh --skip-stage3-sem-controle

demo-fast: permissions
	./scripts/demo_todas_etapas.sh --skip-stage3-sem-controle

demo-full: permissions
	./scripts/demo_todas_etapas.sh --full-etapa2

show-demo-results:
	./scripts/mostrar_resultados_demo.sh
