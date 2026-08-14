from pprint import pprint

from app.services.kubernetes_service import KubernetesService


service = KubernetesService(
    namespace="ai-workloads",
    mode="kubeconfig",
)

result = service.get_nvidia_gpu_capacity()

pprint(result)
