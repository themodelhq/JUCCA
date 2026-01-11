"""
JUCCA Load Testing Configuration
================================

This file contains load testing scenarios for the JUCCA API.
Run with: locust -f locustfile.py

Scenarios:
1. Normal Load Test - Typical user behavior
2. Stress Test - High concurrent users
3. Spike Test - Sudden traffic bursts
4. Endurance Test - Long-running tests
"""

from locust import HttpUser, task, between, events, stats
from locust.runners import MasterRunner
import random
import time
import json

# Configure statistics
stats.PERCENTILES_TO_CHART = [0.5, 0.95, 0.99]


# ============================================
# Test Users
# ============================================

class JUCCAUser(HttpUser):
    """Typical JUCCA user behavior."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """User login simulation."""
        self.token = None
        self.user_type = random.choice(['seller', 'seller', 'seller', 'admin'])
        
        # Simulate login (optional)
        if self.user_type == 'admin':
            response = self.client.post('/token', 
                data={'username': 'admin', 'password': 'admin123'},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            if response.status_code == 200:
                self.token = response.json().get('access_token')
    
    @task(3)
    def ask_compliance_question(self):
        """Main task: Ask compliance questions."""
        questions = [
            "Can I sell Nike shoes in Nigeria?",
            "What about used electronics?",
            "Can I list fake products?",
            "Is Apple iPhone allowed?",
            "Can I sell alcohol?",
            "What brands require authorization?",
            "Can I sell prescription drugs?",
            "Is Gucci allowed?",
            "Can I sell weapons?",
            "What about replica watches?"
        ]
        
        question = random.choice(questions)
        payload = {
            "question": question,
            "session_id": f"test_{int(time.time())}",
            "role": self.user_type
        }
        
        headers = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        with self.client.post('/ask', 
                             json=payload,
                             headers=headers,
                             name='/ask',
                             catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Status {response.status_code}')
    
    @task(1)
    def check_health(self):
        """Health check endpoint."""
        with self.client.get('/health', 
                           name='/health',
                           catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f'Status {response.status_code}')


class JUCCAStressUser(HttpUser):
    """Stress test user with minimal wait time."""
    
    wait_time = between(0.1, 0.5)
    
    @task(5)
    def rapid_ask(self):
        """Rapid compliance questions."""
        questions = [
            "Can I sell Nike shoes?",
            "Is this allowed?",
            "What about fake items?"
        ]
        
        payload = {
            "question": random.choice(questions),
            "session_id": f"stress_{int(time.time())}",
            "role": "seller"
        }
        
        self.client.post('/ask', json=payload, name='/ask_stress')
    
    @task(1)
    def health_check(self):
        """Rapid health checks."""
        self.client.get('/health', name='/health_stress')


class JUCCASpikeUser(HttpUser):
    """Spike test user - burst traffic."""
    
    wait_time = between(0.01, 0.1)
    
    @task(10)
    def spike_questions(self):
        """Burst of questions."""
        payload = {
            "question": "Can I sell Nike shoes?",
            "session_id": f"spike_{int(time.time())}",
            "role": "seller"
        }
        
        self.client.post('/ask', json=payload, name='/ask_spike')


# ============================================
# Load Test Scenarios
# ============================================

class NormalLoadTest(HttpUser):
    """Normal load test configuration."""
    
    wait_time = between(2, 5)
    tasks = [JUCCAUser]
    
    # Spawn 50 users over 30 seconds
    @classmethod
    def weight(cls):
        return 10


class StressTest(HttpUser):
    """Stress test configuration."""
    
    wait_time = between(0.5, 1)
    tasks = [JUCCAStressUser]
    
    @classmethod
    def weight(cls):
        return 5


class SpikeTest(HttpUser):
    """Spike test configuration."""
    
    wait_time = between(0.1, 0.2)
    tasks = [JUCCASpikeUser]
    
    @classmethod
    def weight(cls):
        return 2


# ============================================
# Custom Events
# ============================================

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize custom metrics."""
    if isinstance(environment.runner, MasterRunner):
        print("JUCCA Load Test initialized")
        print(f"Target: {environment.host}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Print test start information."""
    print("\n" + "="*50)
    print("JUCCA Load Test Starting")
    print("="*50)
    print("Test scenarios:")
    print("  1. Normal Load - 50 concurrent users")
    print("  2. Stress Test - High concurrency")
    print("  3. Spike Test - Burst traffic")
    print("="*50 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print test summary."""
    print("\n" + "="*50)
    print("JUCCA Load Test Completed")
    print("="*50)
    
    # Print summary statistics
    stats_report = environment.stats
    print("\nTop Endpoints by Request Count:")
    for name, data in sorted(stats_report.entries.items(), 
                            key=lambda x: x[1].num_requests, 
                            reverse=True)[:5]:
        print(f"  {name}: {data.num_requests} requests, "
              f"{data.num_failures} failures, "
              f"Avg: {data.avg_response_time:.2f}ms")
    
    print("\n" + "="*50)


# ============================================
# Test Configuration Helpers
# ============================================

def get_test_questions():
    """Get list of test questions for load testing."""
    return [
        "Can I sell Nike shoes in Nigeria?",
        "What about used electronics?",
        "Can I list fake products?",
        "Is Apple iPhone allowed?",
        "Can I sell alcohol?",
        "What brands require authorization?",
        "Can I sell prescription drugs?",
        "Is Gucci allowed?",
        "Can I sell weapons?",
        "What about replica watches?",
        "Can I sell Adidas sneakers?",
        "Is Chanel perfume allowed?",
        "Can I sell Samsung phones?",
        "What about counterfeit items?",
        "Can I sell Omega watches?",
        "Is Louis Vuitton bag allowed?",
        "Can I sell Huawei devices?",
        "What about restricted brands?",
        "Can I sell Rolex watches?",
        "Is Puma clothing allowed?"
    ]


def get_expected_responses():
    """Get expected response patterns for validation."""
    return {
        'Allowed': ['Great news', 'allowed', 'Good news'],
        'Restricted': ['restrictions', 'authorization', 'restricted'],
        'Prohibited': ['cannot be listed', 'prohibited', 'Sorry'],
        'Blocked': ['blocked', 'violates', 'unable']
    }
