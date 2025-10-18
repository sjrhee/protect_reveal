# Ubuntu 22.04 Kubernetes(kubeadm 기반) 구축 및 복구 절차

---

## 1. 기본 환경 구성
| 역할 | 호스트 이름 | IP 주소 |
|------|--------------|----------|
| Master | k8s-master | 192.168.0.231 |
| Worker | k8s-worker | 192.168.0.232 |

### 사전 설정
```bash
sudo hostnamectl set-hostname k8s-master   # 마스터
sudo hostnamectl set-hostname k8s-worker   # 워커

sudo vi /etc/hosts
192.168.0.231 k8s-master
192.168.0.232 k8s-worker

sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab
```

### 커널 모듈 및 네트워크 설정
```bash
sudo modprobe overlay
sudo modprobe br_netfilter
sudo tee /etc/sysctl.d/kubernetes.conf <<EOF
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
sudo sysctl --system
```

---

## 2. Containerd 런타임 설치
```bash
sudo apt update
sudo apt install -y containerd
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
```

CRI 상태 확인:
```bash
sudo crictl info | grep runtimeType
sudo ctr version
```

---

## 3. kubeadm / kubelet / kubectl 설치
```bash
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /" | sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt update
K8S_VERSION="1.30.4-1.1"
sudo apt install -y kubelet=$K8S_VERSION kubeadm=$K8S_VERSION kubectl=$K8S_VERSION
sudo apt-mark hold kubelet kubeadm kubectl
```

---

## 4. 방화벽 설정 (UFW 기준)
```bash
sudo ufw allow 6443/tcp
sudo ufw allow 2379:2380/tcp
sudo ufw allow 10250/tcp
sudo ufw allow 30000:32767/tcp
```
or
```bash
sudo systemctl stop ufw
sudo systemctl disable ufw
```

---

## 5. 마스터 초기화 및 네트워크 구성
```bash
sudo kubeadm init --apiserver-advertise-address=192.168.0.231 \
  --pod-network-cidr=10.244.0.0/16

mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/v0.25.5/Documentation/kube-flannel.yml
```

Flannel 확인:
```bash
kubectl get pods -n kube-flannel
```

---

## 6. 워커 노드 조인
```bash
sudo kubeadm join 192.168.0.231:6443 --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash>
```

토큰 만료 시:
```bash
sudo kubeadm token create --print-join-command
```

---

## 7. NGINX 배포 및 테스트
```bash
kubectl create deployment nginx --image=nginx
kubectl expose deployment nginx --port=80 --type=NodePort
kubectl get svc
# 브라우저 접속 예: http://192.168.0.232:<NodePort>
```

---

## 8. Helm 설치 및 검증
```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install my-nginx bitnami/nginx --set service.type=NodePort
helm list
kubectl get all -l app.kubernetes.io/name=nginx
```

---

## 9. 재부팅 후 복구 절차
```bash
sudo systemctl daemon-reexec
sudo systemctl restart containerd kubelet
sudo systemctl enable containerd kubelet

kubectl get nodes -o wide
kubectl get pods -A -o wide
```

Flannel 오류 시 재적용:
```bash
kubectl delete -f https://raw.githubusercontent.com/flannel-io/flannel/v0.25.5/Documentation/kube-flannel.yml
kubectl apply  -f https://raw.githubusercontent.com/flannel-io/flannel/v0.25.5/Documentation/kube-flannel.yml
```

---

## 10. 로그 및 진단 명령어
```bash
sudo journalctl -u kubelet -f
sudo journalctl -u containerd -f
kubectl get events -A --sort-by=.metadata.creationTimestamp
kubectl logs -n kube-flannel -l app=flannel --tail=50
```

---

## 11. 시스템 자동복구 설정 (확인용)
```bash
sudo systemctl enable containerd kubelet
sudo tee /etc/sysctl.d/kubernetes.conf <<EOF
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
sudo sysctl --system
```

---

## 12. 정상 상태 점검 명령어
```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl get svc -A
```

---

✅ **요약**
- kubeadm, kubelet, kubectl 버전 고정 (`apt-mark hold`)
- CRI/CNI 상태 점검 명령 추가
- 방화벽 포트 개방 명시
- 재부팅 후 daemon 재실행 추가 (`daemon-reexec`)
- Helm Chart 배포 검증 절차 추가
- 주요 로그 진단 명령 강화

