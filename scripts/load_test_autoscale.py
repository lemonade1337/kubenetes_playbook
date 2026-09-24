#!/usr/bin/env python3
"""
Concurrency Load Tester for Qwen 2.5 3B Kubernetes Autoscaling
Simulates multiple concurrent user requests to saturate active Qwen instances
and trigger Horizontal Pod Autoscaler (HPA) scale-up from 1 to 6 instances.
"""

import sys
import time
import requests
import concurrent.futures

BASE_URL = "http://localhost:30080"
if len(sys.argv) > 1:
    BASE_URL = sys.argv[1]

CONCURRENT_USERS = 6
REQUESTS_PER_USER = 2

API_KEYS = [
    "sk-admin-master-key-2026",
    "sk-user1-secret-key-2026",
    "sk-user2-secret-key-2026",
    "sk-user3-secret-key-2026"
]

def send_heavy_request(user_index, req_id):
    api_key = API_KEYS[user_index % len(API_KEYS)]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": "You are a detailed technical writer."},
            {"role": "user", "content": f"Write a comprehensive 300-word explanation of distributed consensus in Kubernetes. Request #{req_id}"}
        ],
        "temperature": 0.7,
        "max_tokens": 400
    }

    print(f"🔥 [User {user_index+1}] Sending generation request #{req_id}...")
    start = time.time()
    try:
        r = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload, timeout=120)
        dur = time.time() - start
        if r.status_code == 200:
            tokens = r.json().get("usage", {}).get("total_tokens", 0)
            print(f"✅ [User {user_index+1}] Completed in {dur:.2f}s ({tokens} tokens)")
            return True, dur
        else:
            print(f"❌ [User {user_index+1}] Failed with status {r.status_code}: {r.text}")
            return False, dur
    except Exception as e:
        print(f"⚠️ [User {user_index+1}] Error: {e}")
        return False, 0

def main():
    print("===================================================================")
    print("🚀 Qwen 2.5 3B Autoscaling Load Test")
    print(f"Simulating {CONCURRENT_USERS} concurrent streams to trigger HPA scaling (1 -> 6 pods)...")
    print(f"Watch HPA in another terminal with: kubectl get hpa -n llm-platform -w")
    print(f"Watch Pods in another terminal with: kubectl get pods -n llm-platform -l app=qwen-llm -w")
    print("===================================================================")

    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        for u in range(CONCURRENT_USERS):
            for r in range(REQUESTS_PER_USER):
                tasks.append(executor.submit(send_heavy_request, u, r+1))

        results = [t.result() for t in concurrent.futures.as_completed(tasks)]

    success_count = sum(1 for s, _ in results if s)
    print("===================================================================")
    print(f"📊 Load Test Finished: {success_count}/{len(tasks)} requests completed successfully.")
    print("Check scaling status with: kubectl get pods -n llm-platform -l app=qwen-llm")
    print("===================================================================")

if __name__ == "__main__":
    main()
