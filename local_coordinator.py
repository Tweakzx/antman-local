import etcd3
import json
import os 
import time
import threading
import subprocess
from kubernetes import client, config

# 创建 etcd 客户端对象
os.environ["ETCDCTL_APP"] = "3"
cer_pre = '/etc/kubernetes/pki/etcd/'
etcd_client = etcd3.client(host='10.10.108.91',port=2379, ca_cert=cer_pre+'ca.crt', cert_cert=cer_pre+'etcd-client.crt', cert_key=cer_pre+'etcd-client.key')
node_name = "h14"

# 创建k8sAPi客户端
config.load_incluster_config()
v1 = client.CoreV1Api()

def read_gpu_utilization():
    while True:
        time.sleep(1)
        output = subprocess.check_output(["nvidia-smi", "--query-gpu=gpu_bus_id,memory.used,memory.total,utilization.gpu", "--format=csv,noheader"])
        for line in output.decode("utf-8").strip().split("\n"):
            bus_id, memory_used, memory_total, gpu_utilization = line.split(",")
            key_prefix = f"{node_name}/gpu/{bus_id}"
            etcd_client.put(f"{key_prefix}/memory/used", memory_used.strip())
            etcd_client.put(f"{key_prefix}/memory/total", memory_total.strip())
            etcd_client.put(f"{key_prefix}/utilization/gpu", gpu_utilization.strip())
            print('write gpu info to etcd')

# 读取JSON文件的函数
def read_json_file():
    filename = '/status.json'
    antman_dir = '/tmp/antman/'

    modified_time = {}
    # for pod_folder in os.listdir(antman_dir):
    #     status_file_dir = antman_dir + pod_folder + filename
    #     modified_time[status_file_dir] = os.path.getmtime(status_file_dir)
    
    while True:
    # 每秒钟检查一次文件是否被修改
        time.sleep(1)
        for pod_folder in os.listdir(antman_dir):
            status_file_dir = antman_dir + pod_folder + filename
            current_modified_time = os.path.getmtime(status_file_dir)
            if current_modified_time != modified_time.get(status_file_dir, 0):
                modified_time[status_file_dir] = current_modified_time
                with open(status_file_dir, 'r') as f:
                    json_data = json.load(f)
                data = json.dumps(json_data)
                etcd_client.put(f"antman/{node_name}/podname/data", data)
                print(pod_folder + 'status file changed, and write to etcd')
                manage_job()

def manage_job():
    print("start rearrange job")
    # 获取当前 node 的名称
    node_name = os.environ['HOSTNAME']
    pod_list = v1.list_pod_for_all_namespaces().items

    gpu2pod = {}
    for pod in pod_list:
        if pod.spec.node_name == node_name:
            gpu2pod[pod.spec.gpuDevices].append(pod)    

    for bus_id, pods in gpu2pod:
        prefix = f"antman/{node_name}/gpu/{bus_id}/"
        gpu_mem_total = client.get(f"{prefix}memory/total")
        gpu_util_total = 100
        opp_cnt = 0
        for pod in pods :
            if pod.spec.type == "resource-guarantee" :
                gpu_rsj_mem = client.get()
                gpu_rsj_util = client.get()
                gpu_mem_total -= gpu_rsj_mem
                gpu_util_total -= gpu_rsj_util
            elif pod.spec.type == "opportunitistic" :
                opp_cnt += 1
        
        gpu_mem_average = gpu_mem_total / opp_cnt 
        gpu_util_averarge = gpu_util_total / opp_cnt
        for pod in pods:
            set_config(pod, bus_id, gpu_mem_average, gpu_util_averarge)

def set_config(pod, bus_id, gpu_mem_average, gpu_util_averarge):
    data = {
        "gpuConfigInfo" : {
            f"{bus_id}":gpu_mem_average    
        },
        "perfControl": gpu_util_averarge
    }
    with open('/tmp/antman/tfjob-zxcvb/config.json', 'w') as f:
        json.dump(data, f)


def coordinate_config():
    pass

if __name__ == '__main__':
    # 创建两个子线程
    t1 = threading.Thread(target=read_gpu_utilization)
    t2 = threading.Thread(target=read_json_file)

    # 启动子线程
    t1.start()
    t2.start()

    # 等待子线程结束
    t1.join()
    t2.join()