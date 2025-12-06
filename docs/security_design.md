# Wyrdflow Security Design Document

**Version**: 1.0
**Date**: December 5, 2025
**Status**: Design / Research Phase
**Phase**: 7 - Security & Execution Research

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Threat Model](#threat-model)
3. [Python Code Execution Sandboxing](#python-code-execution-sandboxing)
4. [Secrets Management](#secrets-management)
5. [Multi-Tenancy Architecture](#multi-tenancy-architecture)
6. [Resource Limits & Quotas](#resource-limits--quotas)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Compliance Considerations](#compliance-considerations)
9. [Risk Assessment](#risk-assessment)
10. [Recommendations](#recommendations)

---

## Executive Summary

This document outlines the security architecture for Wyrdflow, focusing on safe execution of arbitrary Python code, secrets management, and multi-tenancy support. The key design goals are:

- **Security by default**: All code execution is sandboxed
- **Defense in depth**: Multiple layers of security controls
- **Usability**: Security doesn't impede developer productivity
- **Compliance ready**: GDPR, SOC2, and enterprise requirements

### Key Recommendations

1. **Code Execution**: Use **RestrictedPython** with process-level isolation for Phase 8
2. **Secrets Management**: Environment variables + HashiCorp Vault integration
3. **Multi-Tenancy**: Process-level isolation with resource quotas (future phase)
4. **Resource Limits**: cgroups + Python resource module for enforcement

---

## Threat Model

### Assets to Protect

1. **Workflow State Data**
   - User data flowing through workflows
   - API keys and credentials
   - Proprietary business logic

2. **System Resources**
   - CPU, memory, disk, network
   - Database connections
   - External API quotas

3. **Intellectual Property**
   - Workflow definitions
   - Custom node implementations
   - Training data and models

### Threat Actors

1. **Malicious Users**
   - Intent: Steal data, disrupt service, gain unauthorized access
   - Capability: Can submit arbitrary workflows and code
   - Access: Authenticated user account

2. **Compromised Workflows**
   - Intent: Exfiltrate data, escalate privileges
   - Capability: Exploit vulnerabilities in dependencies
   - Access: Execution within workflow context

3. **Insider Threats**
   - Intent: Data theft, sabotage
   - Capability: Access to internal systems
   - Access: Employee/contractor credentials

### Attack Vectors

1. **Code Injection**
   - **Risk**: HIGH
   - **Description**: Malicious code in CodeNode or custom functions
   - **Impact**: System compromise, data theft
   - **Mitigation**: Sandboxing, AST validation, import restrictions

2. **Resource Exhaustion**
   - **Risk**: HIGH
   - **Description**: Infinite loops, memory bombs, fork bombs
   - **Impact**: Denial of service
   - **Mitigation**: CPU/memory/time limits, process isolation

3. **Data Exfiltration**
   - **Risk**: MEDIUM
   - **Description**: Stealing secrets or workflow data
   - **Impact**: Data breach, compliance violation
   - **Mitigation**: Network restrictions, audit logging, encryption

4. **Privilege Escalation**
   - **Risk**: MEDIUM
   - **Description**: Escaping sandbox to access host system
   - **Impact**: Full system compromise
   - **Mitigation**: Process isolation, minimal privileges

5. **Dependency Vulnerabilities**
   - **Risk**: MEDIUM
   - **Description**: Exploiting vulnerable packages
   - **Impact**: Various (depends on vulnerability)
   - **Mitigation**: Dependency scanning, allowlist, regular updates

---

## Python Code Execution Sandboxing

### Overview

The CodeNode allows users to execute arbitrary Python code within workflows. This is powerful but dangerous without proper sandboxing.

### Option 1: RestrictedPython ⭐ **RECOMMENDED**

**Description**: A library that provides restricted execution of Python code by rewriting the Abstract Syntax Tree (AST).

**How it works**:
- Compiles Python code to a restricted AST
- Removes dangerous operations (file I/O, imports, exec, eval)
- Provides safe built-ins and controlled environment
- Code runs in same process with restricted globals

**Pros**:
- ✅ Lightweight (no containers or VMs)
- ✅ Fast execution (<10ms overhead)
- ✅ Pure Python (easy to install and maintain)
- ✅ Fine-grained control over allowed operations
- ✅ Can allowlist specific imports
- ✅ Well-maintained (used by Zope, Plone)
- ✅ Good documentation and community support

**Cons**:
- ⚠️ Not foolproof (potential escapes via edge cases)
- ⚠️ Requires careful configuration
- ⚠️ Limited by Python's introspection capabilities
- ⚠️ Same process = shared memory space

**Security Level**: MEDIUM-HIGH (with process isolation)

**Implementation Complexity**: LOW

**Performance Impact**: MINIMAL (<5%)

**Example**:
```python
from RestrictedPython import compile_restricted, safe_globals

code = """
result = sum([1, 2, 3, 4, 5])
"""

byte_code = compile_restricted(code, '<inline>', 'exec')
exec(byte_code, safe_globals)
```

**Recommendation**:
Use RestrictedPython as primary sandboxing mechanism, combined with:
- Process-level isolation (separate process per execution)
- Resource limits (CPU, memory, time)
- Import allowlist (only safe packages)
- Network access control

---

### Option 2: PyPy Sandbox

**Description**: PyPy interpreter with OS-level sandboxing that intercepts all system calls.

**How it works**:
- Runs Python code in sandboxed PyPy interpreter
- All system calls go through external proxy process
- Proxy validates and executes allowed operations
- Complete isolation from host system

**Pros**:
- ✅ Very secure (all syscalls intercepted)
- ✅ Complete isolation
- ✅ Can't escape sandbox (by design)
- ✅ JIT compilation for performance

**Cons**:
- ❌ **Deprecated** (PyPy sandbox is no longer maintained)
- ❌ Complex setup and maintenance
- ❌ Not compatible with all Python packages
- ❌ High overhead (separate process + proxy)
- ❌ Limited PyPy version (stuck on old Python)

**Security Level**: VERY HIGH

**Implementation Complexity**: VERY HIGH

**Performance Impact**: HIGH (30-50% overhead)

**Recommendation**: ❌ **NOT RECOMMENDED** - Deprecated and unmaintained

---

### Option 3: Docker Containers

**Description**: Execute code in isolated Docker containers with resource constraints.

**How it works**:
- Spin up Docker container for each code execution
- Mount minimal filesystem (read-only)
- Apply cgroup limits (CPU, memory, network)
- Destroy container after execution

**Pros**:
- ✅ Very strong isolation
- ✅ Industry standard for containerization
- ✅ Well-understood security model
- ✅ Resource limits enforced by kernel
- ✅ Can use different Python versions
- ✅ Network isolation via Docker networks

**Cons**:
- ⚠️ Heavy (100-500ms startup per container)
- ⚠️ Requires Docker daemon on host
- ⚠️ Complex orchestration for production
- ⚠️ Not suitable for short-lived executions
- ⚠️ Potential container escape vulnerabilities
- ⚠️ Resource overhead (memory, disk)

**Security Level**: HIGH

**Implementation Complexity**: MEDIUM

**Performance Impact**: HIGH (container startup latency)

**Recommendation**: Consider for **batch processing** or **long-running code**, not for individual node executions

---

### Option 4: WebAssembly (WASI)

**Description**: Compile Python to WebAssembly and run in sandboxed WASM runtime.

**How it works**:
- Use PyOdide or similar to run Python in WASM
- WASM runtime provides sandboxed environment
- All system access goes through WASI interface
- Complete memory isolation

**Pros**:
- ✅ Future-proof technology
- ✅ Excellent isolation
- ✅ Fast execution (near-native)
- ✅ Can run in browser or server
- ✅ Growing ecosystem

**Cons**:
- ❌ Experimental/emerging technology
- ❌ Limited Python package support
- ❌ No native extensions (C libraries)
- ❌ Complex toolchain
- ❌ Still maturing for server-side use

**Security Level**: VERY HIGH

**Implementation Complexity**: VERY HIGH

**Performance Impact**: MEDIUM (WASM overhead)

**Recommendation**: ⏰ **FUTURE CONSIDERATION** - Wait for ecosystem maturity

---

### Option 5: Process Isolation (subprocess)

**Description**: Run code in separate Python process with restricted permissions.

**How it works**:
- Spawn new Python process via subprocess
- Pass code and inputs via stdin/environment
- Apply OS-level limits (ulimit, cgroups)
- Capture output and kill process on timeout
- Drop privileges (run as restricted user)

**Pros**:
- ✅ Strong isolation (separate process)
- ✅ No shared memory with parent
- ✅ Easy to implement
- ✅ Works with all Python packages
- ✅ OS-enforced resource limits
- ✅ Process can be killed forcefully

**Cons**:
- ⚠️ Process creation overhead (10-50ms)
- ⚠️ IPC complexity for large data
- ⚠️ Still has access to filesystem
- ⚠️ Requires OS-level privilege management

**Security Level**: MEDIUM-HIGH

**Implementation Complexity**: LOW

**Performance Impact**: MEDIUM (process startup)

**Recommendation**: ✅ **USE AS SECONDARY LAYER** - Combine with RestrictedPython

---

### Recommended Approach: **Layered Security**

Combine multiple techniques for defense in depth:

```
┌─────────────────────────────────────────┐
│  Layer 1: AST Validation                │
│  - Syntax checking                      │
│  - Banned keywords (exec, eval, etc.)   │
│  - Import statement validation          │
└─────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Layer 2: RestrictedPython              │
│  - Compile to restricted AST            │
│  - Safe built-ins only                  │
│  - Controlled globals                   │
└─────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Layer 3: Process Isolation             │
│  - Separate Python process              │
│  - Minimal permissions                  │
│  - No shared memory                     │
└─────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Layer 4: Resource Limits               │
│  - CPU time limit (via signal.alarm)    │
│  - Memory limit (via resource.setrlimit)│
│  - Execution timeout                    │
└─────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Layer 5: Network Restrictions          │
│  - No network access by default         │
│  - Allowlist specific hosts if needed   │
│  - Monitor outbound connections         │
└─────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Layer 6: Audit Logging                 │
│  - Log all code executions              │
│  - Track resource usage                 │
│  - Alert on suspicious activity         │
└─────────────────────────────────────────┘
```

### Implementation Details

**Allowed Operations**:
- Math operations (arithmetic, comparisons)
- String manipulation
- List/dict operations
- Function definitions and calls
- Loops (with iteration limits)
- Conditional statements

**Restricted Operations**:
- File I/O (open, read, write)
- Network access (socket, urllib)
- Process execution (os.system, subprocess)
- Code execution (exec, eval, compile)
- Reflection (getattr, setattr on protected objects)
- Module imports (except allowlist)

**Allowed Imports** (Phase 8):
```python
ALLOWED_MODULES = [
    # Data manipulation
    "pandas", "numpy", "json", "csv",

    # Date/time
    "datetime", "time",

    # Math
    "math", "statistics", "decimal", "fractions",

    # Text processing
    "re", "string", "textwrap",

    # Collections
    "collections", "itertools", "functools",
]
```

**Execution Limits**:
```python
RESOURCE_LIMITS = {
    "max_execution_time": 30,  # seconds
    "max_memory": 512 * 1024 * 1024,  # 512MB
    "max_output_size": 10 * 1024 * 1024,  # 10MB
    "max_iterations": 1_000_000,  # prevent infinite loops
}
```

---

## Secrets Management

### Overview

Workflows often need access to sensitive credentials (API keys, database passwords, etc.). Secure secrets management is critical to prevent data breaches.

### Requirements

1. **Never log secrets**: Secrets must not appear in logs, traces, or error messages
2. **Encryption at rest**: Secrets stored encrypted on disk
3. **Encryption in transit**: TLS for all secret access
4. **Access control**: Only authorized workflows can access secrets
5. **Audit logging**: All secret access is logged (but not the secret values)
6. **Key rotation**: Support for rotating secrets without workflow changes
7. **Multi-environment**: Different secrets for dev/staging/prod

### Option 1: Environment Variables ⭐ **RECOMMENDED FOR MVP**

**Description**: Store secrets as environment variables, loaded at runtime.

**How it works**:
```python
import os

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")
```

**Pros**:
- ✅ Simple to implement
- ✅ No external dependencies
- ✅ 12-factor app compliant
- ✅ Works everywhere (local, Docker, K8s)
- ✅ IDE support (.env files)

**Cons**:
- ⚠️ Secrets visible in process environment
- ⚠️ No encryption at rest
- ⚠️ No audit logging
- ⚠️ Manual rotation
- ⚠️ Limited to string values

**Security Level**: LOW-MEDIUM

**Recommendation**: ✅ **Use for Phase 8 MVP**, with .env file support for development

---

### Option 2: HashiCorp Vault ⭐ **RECOMMENDED FOR PRODUCTION**

**Description**: Industry-standard secrets management system with encryption, access control, and audit logging.

**How it works**:
```python
import hvac

client = hvac.Client(url='https://vault.example.com')
client.token = os.getenv('VAULT_TOKEN')

secret = client.secrets.kv.v2.read_secret_version(
    path='wyrdflow/prod/openai'
)
api_key = secret['data']['data']['api_key']
```

**Pros**:
- ✅ Enterprise-grade security
- ✅ Encryption at rest and in transit
- ✅ Fine-grained access control (policies)
- ✅ Comprehensive audit logging
- ✅ Automatic secret rotation
- ✅ Dynamic secrets (generate on demand)
- ✅ Multi-cloud support
- ✅ UI for management

**Cons**:
- ⚠️ Requires Vault server (operational overhead)
- ⚠️ Complex initial setup
- ⚠️ Network dependency
- ⚠️ Cost (for managed Vault)

**Security Level**: VERY HIGH

**Recommendation**: ✅ **Implement for production deployments** (Phase 9+)

---

### Option 3: Cloud Provider Secret Managers

**AWS Secrets Manager**:
```python
import boto3

client = boto3.client('secretsmanager')
response = client.get_secret_value(SecretId='wyrdflow/prod/openai')
secret = json.loads(response['SecretString'])
```

**Google Secret Manager**:
```python
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
name = 'projects/123/secrets/openai/versions/latest'
response = client.access_secret_version(request={"name": name})
secret = response.payload.data.decode('UTF-8')
```

**Azure Key Vault**:
```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://myvault.vault.azure.net/", credential=credential)
secret = client.get_secret("openai-api-key")
```

**Pros**:
- ✅ Managed service (no ops)
- ✅ High availability
- ✅ Integrated with cloud IAM
- ✅ Automatic encryption
- ✅ Audit logging

**Cons**:
- ⚠️ Cloud provider lock-in
- ⚠️ Cost per secret + API calls
- ⚠️ Requires cloud credentials

**Security Level**: HIGH

**Recommendation**: ✅ **Support as plugin** for cloud-native deployments

---

### Option 4: Encrypted Configuration Files

**Description**: Store secrets in encrypted files, decrypt at runtime.

**How it works**:
```python
from cryptography.fernet import Fernet

# Load encryption key from environment
key = os.getenv('WYRDFLOW_ENCRYPTION_KEY').encode()
cipher = Fernet(key)

# Decrypt secrets file
with open('secrets.enc', 'rb') as f:
    encrypted_data = f.read()

decrypted_data = cipher.decrypt(encrypted_data)
secrets = json.loads(decrypted_data)
```

**Pros**:
- ✅ Works offline
- ✅ No external dependencies
- ✅ Version control friendly (encrypted)
- ✅ Simple to implement

**Cons**:
- ⚠️ Key management problem (where to store the key?)
- ⚠️ Manual rotation
- ⚠️ No audit logging
- ⚠️ Risk of committing unencrypted secrets

**Security Level**: MEDIUM

**Recommendation**: ⚠️ **NOT RECOMMENDED** - Key management too complex

---

### Recommended Secrets Architecture

**Phase 8 (MVP)**:
```python
class SecretsManager:
    """Simple secrets manager using environment variables."""

    def get_secret(self, key: str) -> str:
        """Get secret from environment."""
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Secret '{key}' not found in environment")
        return value

    def load_from_dotenv(self, path: str = ".env"):
        """Load secrets from .env file (development only)."""
        from dotenv import load_dotenv
        load_dotenv(path)
```

**Phase 9+ (Production)**:
```python
class SecretsManager:
    """Pluggable secrets manager with multiple backends."""

    def __init__(self, backend: str = "env"):
        self.backend = self._create_backend(backend)

    def _create_backend(self, backend: str):
        if backend == "env":
            return EnvironmentBackend()
        elif backend == "vault":
            return VaultBackend()
        elif backend == "aws":
            return AWSSecretsBackend()
        elif backend == "gcp":
            return GCPSecretsBackend()
        elif backend == "azure":
            return AzureKeyVaultBackend()
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def get_secret(self, key: str) -> str:
        value = self.backend.get(key)
        self._audit_log(key)  # Log access (not value!)
        return value
```

**Audit Logging**:
```python
def _audit_log(self, secret_key: str):
    """Log secret access for security audit."""
    logger.info(
        "Secret accessed",
        extra={
            "secret_key": secret_key,  # Log key name
            "workflow_id": self.context.workflow_id,
            "user_id": self.context.user_id,
            "timestamp": datetime.now().isoformat(),
        }
    )
    # NEVER log the actual secret value!
```

**Never Log Secrets**:
```python
def sanitize_for_logging(data: dict) -> dict:
    """Remove sensitive fields from data before logging."""
    SENSITIVE_KEYS = [
        "api_key", "password", "token", "secret",
        "auth", "credential", "private_key"
    ]

    sanitized = data.copy()
    for key in sanitized:
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            sanitized[key] = "***REDACTED***"

    return sanitized
```

---

## Multi-Tenancy Architecture

### Overview

Multi-tenancy allows multiple organizations/users to share the same Wyrdflow infrastructure while maintaining isolation and security.

**Note**: This is for **future implementation** (post-v1.0), but we design the architecture now to avoid costly refactoring later.

### Isolation Requirements

1. **Data Isolation**: Tenants cannot access each other's data
2. **Resource Isolation**: One tenant can't exhaust resources for others
3. **Performance Isolation**: One tenant's load doesn't affect others
4. **Security Isolation**: Vulnerability in one tenant doesn't affect others

### Option 1: Process-Level Isolation ⭐ **RECOMMENDED**

**Description**: Run each tenant's workflows in separate OS processes.

**Architecture**:
```
┌─────────────────────────────────────────────┐
│  API Gateway (Tenant Router)                │
│  - Authenticates requests                   │
│  - Routes to tenant's worker pool           │
└─────────────────────────────────────────────┘
               ↓
┌─────────────┬─────────────┬─────────────────┐
│  Tenant A   │  Tenant B   │  Tenant C       │
│  Worker     │  Worker     │  Worker         │
│  Pool       │  Pool       │  Pool           │
│  (3 procs)  │  (5 procs)  │  (2 procs)      │
└─────────────┴─────────────┴─────────────────┘
```

**Pros**:
- ✅ Strong isolation (separate memory space)
- ✅ Easy to implement resource quotas
- ✅ Process crash doesn't affect other tenants
- ✅ Can use OS-level permissions
- ✅ Simple to monitor and debug

**Cons**:
- ⚠️ Higher memory usage (multiple processes)
- ⚠️ IPC overhead for shared resources
- ⚠️ More complex orchestration

**Security Level**: HIGH

**Recommendation**: ✅ **PRIMARY ISOLATION METHOD**

---

### Option 2: Namespace Isolation

**Description**: Use Python namespaces and context managers to isolate tenant data.

**Implementation**:
```python
class TenantContext:
    """Context manager for tenant-specific execution."""

    current_tenant = ContextVar('current_tenant', default=None)

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.token = None

    def __enter__(self):
        self.token = self.current_tenant.set(self.tenant_id)
        return self

    def __exit__(self, *args):
        self.current_tenant.reset(self.token)

# Usage
with TenantContext("tenant_a"):
    # All operations here are scoped to tenant_a
    workflow.run()
```

**Pros**:
- ✅ Low overhead (same process)
- ✅ Fast context switching
- ✅ Easy to implement

**Cons**:
- ⚠️ Weak isolation (shared memory)
- ⚠️ Requires careful programming
- ⚠️ Easy to make mistakes (data leakage)

**Security Level**: LOW

**Recommendation**: ⚠️ **USE AS SECONDARY LAYER** only

---

### Option 3: Container-Per-Tenant

**Description**: Each tenant gets dedicated Docker containers/pods.

**Architecture** (Kubernetes):
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-a
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wyrdflow-worker
  namespace: tenant-a
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: worker
        image: wyrdflow:latest
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
```

**Pros**:
- ✅ Very strong isolation
- ✅ Industry-standard approach
- ✅ Resource quotas enforced by orchestrator
- ✅ Easy to scale per tenant
- ✅ Separate logs and metrics

**Cons**:
- ⚠️ Requires Kubernetes or similar
- ⚠️ Higher resource overhead
- ⚠️ More complex deployment
- ⚠️ Higher operational cost

**Security Level**: VERY HIGH

**Recommendation**: ✅ **FOR ENTERPRISE/LARGE-SCALE** deployments

---

### Resource Quotas

**Per-Tenant Quotas**:
```python
class TenantQuota(BaseModel):
    """Resource quotas for a tenant."""

    # Workflow execution limits
    max_concurrent_workflows: int = 10
    max_workflows_per_day: int = 1000
    max_workflow_duration: int = 3600  # seconds

    # Resource limits
    max_memory_per_workflow: int = 1024 * 1024 * 1024  # 1GB
    max_cpu_per_workflow: float = 2.0  # cores

    # LLM usage limits
    max_tokens_per_day: int = 1_000_000
    max_llm_cost_per_day: float = 100.0  # USD

    # Storage limits
    max_state_size: int = 100 * 1024 * 1024  # 100MB
    max_workflow_definitions: int = 100

    # API limits
    max_api_calls_per_minute: int = 60
```

**Quota Enforcement**:
```python
class QuotaEnforcer:
    """Enforce tenant quotas."""

    def check_quota(self, tenant_id: str, resource: str) -> bool:
        """Check if tenant has quota available."""
        quota = self.get_tenant_quota(tenant_id)
        usage = self.get_current_usage(tenant_id, resource)

        if usage >= quota[resource]:
            self.log_quota_exceeded(tenant_id, resource)
            raise QuotaExceededError(
                f"Tenant {tenant_id} exceeded quota for {resource}"
            )

        return True
```

---

### Cost Allocation & Billing

**Cost Tracking**:
```python
class CostTracker:
    """Track costs per tenant for billing."""

    def record_llm_cost(
        self,
        tenant_id: str,
        model: str,
        tokens: int,
        cost: float
    ):
        """Record LLM API cost."""
        self.db.insert({
            "tenant_id": tenant_id,
            "resource_type": "llm",
            "model": model,
            "tokens": tokens,
            "cost_usd": cost,
            "timestamp": datetime.now(),
        })

    def get_monthly_bill(self, tenant_id: str) -> dict:
        """Calculate monthly bill for tenant."""
        costs = self.db.query(
            tenant_id=tenant_id,
            start_date=self.month_start(),
            end_date=self.month_end(),
        )

        return {
            "llm_costs": sum(c["cost_usd"] for c in costs if c["resource_type"] == "llm"),
            "compute_costs": sum(c["cost_usd"] for c in costs if c["resource_type"] == "compute"),
            "storage_costs": sum(c["cost_usd"] for c in costs if c["resource_type"] == "storage"),
            "total": sum(c["cost_usd"] for c in costs),
        }
```

---

## Resource Limits & Quotas

### Overview

Prevent resource exhaustion attacks and ensure fair resource allocation.

### CPU Limits

**Using signal.alarm()** (Unix/Linux):
```python
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Execution timed out")

def execute_with_timeout(func, timeout_seconds: int):
    """Execute function with CPU time limit."""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        result = func()
        signal.alarm(0)  # Cancel alarm
        return result
    except TimeoutError:
        logger.warning(f"Function exceeded {timeout_seconds}s timeout")
        raise
```

**Using resource module**:
```python
import resource

def set_cpu_limit(max_cpu_seconds: int):
    """Limit CPU time for current process."""
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (max_cpu_seconds, max_cpu_seconds)
    )
```

---

### Memory Limits

**Using resource module**:
```python
def set_memory_limit(max_memory_bytes: int):
    """Limit memory usage for current process."""
    resource.setrlimit(
        resource.RLIMIT_AS,
        (max_memory_bytes, max_memory_bytes)
    )
```

**Using psutil for monitoring**:
```python
import psutil
import os

def check_memory_usage(max_memory_mb: int):
    """Check if process exceeds memory limit."""
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024

    if memory_mb > max_memory_mb:
        raise MemoryError(f"Process exceeded {max_memory_mb}MB memory limit")
```

---

### Network Access Control

**Disable network by default**:
```python
import socket

class NetworkRestrictedEnvironment:
    """Disable network access for sandboxed code."""

    def __init__(self):
        self.original_socket = socket.socket

    def __enter__(self):
        # Replace socket with disabled version
        socket.socket = self._disabled_socket
        return self

    def __exit__(self, *args):
        # Restore original socket
        socket.socket = self.original_socket

    def _disabled_socket(self, *args, **kwargs):
        raise PermissionError("Network access not allowed in sandboxed code")

# Usage
with NetworkRestrictedEnvironment():
    exec(user_code)  # Cannot make network requests
```

**Allowlist specific hosts**:
```python
class AllowlistNetworkEnvironment:
    """Allow network access only to specific hosts."""

    ALLOWED_HOSTS = [
        "api.openai.com",
        "api.anthropic.com",
    ]

    def _restricted_socket(self, *args, **kwargs):
        # Allow socket creation, but validate on connect
        sock = self.original_socket(*args, **kwargs)

        original_connect = sock.connect

        def validated_connect(address):
            host = address[0] if isinstance(address, tuple) else address
            if host not in self.ALLOWED_HOSTS:
                raise PermissionError(f"Connection to {host} not allowed")
            return original_connect(address)

        sock.connect = validated_connect
        return sock
```

---

### File System Restrictions

**Read-only filesystem**:
```python
import os
import builtins

class ReadOnlyEnvironment:
    """Disable file writes in sandboxed code."""

    def __init__(self):
        self.original_open = builtins.open

    def __enter__(self):
        builtins.open = self._restricted_open
        return self

    def __exit__(self, *args):
        builtins.open = self.original_open

    def _restricted_open(self, file, mode='r', *args, **kwargs):
        if 'w' in mode or 'a' in mode or 'x' in mode or '+' in mode:
            raise PermissionError("Write access not allowed")
        return self.original_open(file, mode, *args, **kwargs)
```

**Restricted temporary directory**:
```python
import tempfile
import shutil

class TempDirectoryEnvironment:
    """Provide isolated temporary directory for file operations."""

    def __init__(self):
        self.temp_dir = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="wyrdflow_")
        os.chdir(self.temp_dir)
        return self.temp_dir

    def __exit__(self, *args):
        # Clean up temporary directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
```

---

## Implementation Roadmap

### Phase 8: Python Code Node (Weeks 1-3)

**Week 1: Foundation**
- [ ] Implement RestrictedPython integration
- [ ] Create AST validator for banned operations
- [ ] Build import allowlist mechanism
- [ ] Write comprehensive tests for sandbox escapes

**Week 2: Process Isolation**
- [ ] Implement subprocess-based code executor
- [ ] Add resource limits (CPU, memory, time)
- [ ] Create IPC mechanism for inputs/outputs
- [ ] Implement timeout and cleanup logic

**Week 3: Security Hardening**
- [ ] Add network access controls
- [ ] Implement filesystem restrictions
- [ ] Create audit logging for code executions
- [ ] Security testing and penetration testing
- [ ] Documentation and examples

**Deliverables**:
- CodeNode class with full sandboxing
- Security documentation
- Example workflows using CodeNode
- Security test suite

---

### Phase 9: Secrets Management (Weeks 1-2)

**Week 1: Basic Implementation**
- [ ] Environment variable backend
- [ ] .env file support for development
- [ ] Secret sanitization in logs
- [ ] Audit logging for secret access

**Week 2: Advanced Backends**
- [ ] HashiCorp Vault integration
- [ ] AWS Secrets Manager integration
- [ ] GCP Secret Manager integration
- [ ] Azure Key Vault integration
- [ ] Plugin architecture for custom backends

**Deliverables**:
- SecretsManager class with multiple backends
- Documentation and examples
- Migration guide from env vars to Vault

---

### Future: Multi-Tenancy (Post-v1.0)

**Phase 1: Foundation**
- [ ] Tenant data model
- [ ] Tenant authentication and authorization
- [ ] Process-level isolation
- [ ] Resource quota system

**Phase 2: Billing**
- [ ] Cost tracking per tenant
- [ ] Usage metrics and reporting
- [ ] Billing integration (Stripe)

**Phase 3: Enterprise Features**
- [ ] Container-per-tenant support
- [ ] Multi-region deployment
- [ ] High availability

---

## Compliance Considerations

### GDPR (General Data Protection Regulation)

**Requirements**:
1. **Data Minimization**: Only collect necessary data
2. **Right to Erasure**: Ability to delete user data
3. **Data Portability**: Export user data in standard format
4. **Consent Management**: Track and honor user consent
5. **Breach Notification**: Detect and report breaches within 72 hours

**Wyrdflow Implementation**:
```python
class GDPRCompliance:
    """GDPR compliance utilities."""

    def export_user_data(self, user_id: str) -> dict:
        """Export all user data for GDPR compliance."""
        return {
            "workflows": self.get_user_workflows(user_id),
            "executions": self.get_user_executions(user_id),
            "logs": self.get_user_logs(user_id),
            "metadata": self.get_user_metadata(user_id),
        }

    def delete_user_data(self, user_id: str):
        """Delete all user data (right to erasure)."""
        self.delete_workflows(user_id)
        self.delete_executions(user_id)
        self.delete_logs(user_id)
        self.anonymize_audit_logs(user_id)
```

---

### SOC 2 (System and Organization Controls)

**Trust Service Criteria**:
1. **Security**: Protection against unauthorized access
2. **Availability**: System is available for operation and use
3. **Processing Integrity**: System processing is complete, valid, accurate
4. **Confidentiality**: Confidential information is protected
5. **Privacy**: Personal information is collected, used, retained, and disclosed properly

**Wyrdflow Implementation**:
- Audit logging for all operations
- Access controls and authentication
- Encryption at rest and in transit
- Regular security assessments
- Incident response procedures

---

### HIPAA (Healthcare)

**Requirements** (if handling PHI):
1. Access controls and authentication
2. Audit logging
3. Data encryption
4. Business associate agreements
5. Breach notification

**Recommendation**: ⚠️ Wyrdflow should **NOT** be used for PHI without extensive additional hardening. Recommend customers use dedicated HIPAA-compliant infrastructure.

---

## Risk Assessment

### Critical Risks (Address in Phase 8)

| Risk | Probability | Impact | Mitigation | Priority |
|------|-------------|--------|------------|----------|
| Sandbox escape | MEDIUM | CRITICAL | Layered security, regular testing | P0 |
| Secret leakage in logs | MEDIUM | HIGH | Log sanitization, audit | P0 |
| Resource exhaustion | HIGH | MEDIUM | Resource limits, quotas | P0 |
| Dependency vulnerabilities | MEDIUM | HIGH | Scanning, allowlist | P1 |

### High Risks (Monitor ongoing)

| Risk | Probability | Impact | Mitigation | Priority |
|------|-------------|--------|------------|----------|
| Data exfiltration | LOW | HIGH | Network controls, monitoring | P1 |
| Privilege escalation | LOW | CRITICAL | Process isolation, minimal perms | P1 |
| DDoS via workflows | MEDIUM | MEDIUM | Rate limiting, quotas | P2 |
| Supply chain attack | LOW | HIGH | Dependency pinning, verification | P2 |

---

## Recommendations

### Immediate Actions (Phase 8)

1. ✅ **Implement RestrictedPython** as primary sandboxing mechanism
2. ✅ **Add process isolation** for defense in depth
3. ✅ **Enforce resource limits** (CPU, memory, time, network)
4. ✅ **Use environment variables** for secrets (MVP)
5. ✅ **Sanitize all logs** to prevent secret leakage
6. ✅ **Audit all code executions** for security monitoring

### Near-Term (Phase 9)

1. ✅ **Integrate HashiCorp Vault** for production secrets
2. ✅ **Add cloud provider integrations** (AWS, GCP, Azure)
3. ✅ **Implement secret rotation** support
4. ✅ **Enhanced audit logging** with alerting

### Long-Term (Post-v1.0)

1. ✅ **Multi-tenancy implementation** with process isolation
2. ✅ **Container-per-tenant** for enterprise
3. ✅ **SOC 2 compliance** audit and certification
4. ✅ **Penetration testing** by third-party security firm

### Security Best Practices

**For Developers**:
1. Never trust user input
2. Validate all data at boundaries
3. Fail securely (deny by default)
4. Keep dependencies up-to-date
5. Review all security-related code changes

**For Users**:
1. Use separate credentials per environment
2. Rotate secrets regularly
3. Monitor audit logs for suspicious activity
4. Keep Wyrdflow updated
5. Report security issues responsibly

---

## Conclusion

This security design provides a comprehensive approach to safely executing arbitrary code, managing secrets, and supporting multi-tenancy in Wyrdflow. The layered security model with RestrictedPython + process isolation provides strong protection while maintaining usability.

**Next Steps**:
1. Review and approve this design document
2. Begin Phase 8 implementation (Python Code Node)
3. Regular security reviews during development
4. Third-party security audit before v1.0 release

---

**Document Version**: 1.0
**Last Updated**: December 5, 2025
**Next Review**: Phase 8 completion
