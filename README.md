# ImagePullSecret Service Account Patcher

Simple Python application that takes to the Kubernetes API to add (multiple) `ImagePullSecrets` to all 
ServiceAccounts in the cluster. 

## Motivation

This project was inspired by [titansoft-pte-ltd/imagepullsecret-patcher](https://github.com/titansoft-pte-ltd/imagepullsecret-patcher) 
which, however, only allows to add one private container registry secret to the cluster's service accounts.

## Usage

It is at best used in conjunction with [emberstack/kubernetes-reflector](https://github.com/emberstack/kubernetes-reflector).
Thus this is the complete approach:

1. Install [emberstack/kubernetes-reflector](https://github.com/emberstack/kubernetes-reflector)

```bash
helm repo add emberstack https://emberstack.github.io/helm-charts
helm repo update
helm upgrade --install reflector emberstack/reflector
```

2. Create container registry secrets in the `kube-system` namespace

```bash
kubectl -n kube-system create secret docker-registry <SECRET_NAME_1> --docker-server=<registry.server.de> --docker-username=<username> --docker-password=<password>
kubectl -n kube-system create secret docker-registry <SECRET_NAME_2> --docker-server=<registry.server.de> --docker-username=<username> --docker-password=<password>
```

3. Patch secrets to make them replicable by [emberstack/kubernetes-reflector](https://github.com/emberstack/kubernetes-reflector)

```bash
kubectl -n kube-system patch secret <SECRET_NAME_1> -p '{"metadata": {"annotations": {"reflector.v1.k8s.emberstack.com/reflection-allowed": "true"}}}'
kubectl -n kube-system patch secret <SECRET_NAME_2> -p '{"metadata": {"annotations": {"reflector.v1.k8s.emberstack.com/reflection-allowed": "true"}}}'
```

4. Add your secrets' names to the `REGISTRY_SECRET_NAMES` environment variable in `deployment/deployment.yaml`. 
5. Install devopstales/serviceaccount-patcher

```bash
kubectl apply -f https://raw.githubusercontent.com/devopstales/imagepullsecret-patcher/master/deployment/rbac.yaml
kubectl apply -f https://raw.githubusercontent.com/devopstales/imagepullsecret-patcher/master/deployment/deployment.yaml
```

## Build

```bash
docker buildx build . -t devopstales/imagepullsecret-patcher --platform linux/amd64,linux/arm64 --no-cache
```
