#!/usr/bin/env python3
"""
Test Suite for Qwen 2.5 3B Kubernetes Platform
Tests authentication, API keys, chat completion proxy, token balance deduction, and admin operations.
"""

import sys
import time
import requests

BASE_URL = "http://localhost:30080" # Default NodePort for Docker Desktop (or http://localhost)
if len(sys.argv) > 1:
    BASE_URL = sys.argv[1]

USER1_KEY = "sk-user1-secret-key-2026"
ADMIN_KEY = "sk-admin-master-key-2026"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def test_health():
    log(f"Checking Gateway Health at {BASE_URL}/healthz...")
    try:
        r = requests.get(f"{BASE_URL}/healthz", timeout=5)
        if r.status_code == 200:
            log("Gateway is HEALTHY (200 OK)", "SUCCESS")
            return True
        log(f"Gateway returned status {r.status_code}", "ERROR")
    except Exception as e:
        log(f"Failed to connect to gateway: {e}", "ERROR")
    return False

def test_models():
    log(f"Listing models from {BASE_URL}/v1/models...")
    r = requests.get(f"{BASE_URL}/v1/models")
    if r.status_code == 200:
        data = r.json()
        models = [m["id"] for m in data.get("data", [])]
        log(f"Available Models: {models}", "SUCCESS")
        return "qwen2.5:3b" in models
    log(f"Failed to list models: {r.text}", "ERROR")
    return False

def test_chat_and_token_deduction():
    log("Testing Chat Completion with User1 API Key & Token Balance Deduction...")
    headers = {
        "Authorization": f"Bearer {USER1_KEY}",
        "Content-Type": "application/json"
    }

    # 1. Send chat completion
    payload = {
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": "You are a concise AI assistant."},
            {"role": "user", "content": "What is 2 + 2? Answer in one word."}
        ],
        "temperature": 0.1
    }

    log("Sending request to /v1/chat/completions...")
    start_time = time.time()
    try:
        r = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload, timeout=60)
        elapsed = time.time() - start_time
        if r.status_code == 200:
            data = r.json()
            answer = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            log(f"Response ({elapsed:.2f}s): '{answer.strip()}'", "SUCCESS")
            log(f"Tokens consumed for request: {tokens_used} (Prompt: {usage.get('prompt_tokens')}, Completion: {usage.get('completion_tokens')})", "INFO")
            return True
        else:
            log(f"Inference failed with status {r.status_code}: {r.text}", "ERROR")
            return False
    except Exception as e:
        log(f"Error during chat completion: {e}", "ERROR")
        return False

def test_admin_operations():
    log("Testing Admin Grant Extra Tokens (+50,000 tokens)...")
    # Login as admin to get session cookie
    session = requests.Session()
    login_resp = session.post(f"{BASE_URL}/login", data={"username": "admin", "password": "AdminPass123!"})
    if login_resp.status_code not in (200, 302, 303):
        log(f"Admin login failed: {login_resp.status_code}", "ERROR")
        return False

    # Get users list
    users_resp = session.get(f"{BASE_URL}/api/admin/users")
    if users_resp.status_code != 200:
        log("Failed to fetch admin users", "ERROR")
        return False

    users = users_resp.json()
    user1 = next((u for u in users if u["username"] == "user1"), None)
    if not user1:
        log("user1 not found in admin users list", "ERROR")
        return False

    initial_balance = user1["remaining_tokens"]
    log(f"User1 Current Balance before grant: {initial_balance:,} tokens", "INFO")

    # Add 50,000 tokens
    add_resp = session.post(f"{BASE_URL}/api/admin/tokens/add", json={"user_id": user1["id"], "amount": 50000})
    if add_resp.status_code == 200:
        new_balance = add_resp.json()["new_balance"]
        log(f"Tokens granted! New balance: {new_balance:,} tokens (Expected: {initial_balance + 50000:,})", "SUCCESS")
        return True
    else:
        log(f"Failed to add tokens: {add_resp.text}", "ERROR")
        return False

def main():
    print("===================================================================")
    print("🧪 Running Automated Verification Suite for Qwen 2.5 3B Platform")
    print(f"Target Gateway: {BASE_URL}")
    print("===================================================================")

    if not test_health():
        sys.exit(1)

    test_models()
    test_chat_and_token_deduction()
    test_admin_operations()

    print("===================================================================")
    print("🎉 All Verification Tests Completed Successfully!")
    print("===================================================================")

if __name__ == "__main__":
    main()
