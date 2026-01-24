# Gemini Context: Home Automation & Infrastructure

This `GEMINI.md` provides context for the AI agent interacting with this
repository. This project serves as the Infrastructure-as-Code (IaC) and
configuration management repository for a home automation setup powered by
Kubernetes on Raspberry Pis.

## Project Overview

* **Goal:** Manage a home Kubernetes cluster and home automation devices.
* **Core Technologies:**
  * **Orchestration:** [k3s](https://k3s.io/) (Lightweight Kubernetes).
  * **GitOps:** [Flux CD](https://fluxcd.io/) automatically syncs the cluster
    state with this repository.
  * **Configuration Management:** [Ansible](https://www.ansible.com/) configures
    the bare metal Raspberry Pi nodes.
  * **Home Automation:** [Home Assistant](https://www.home-assistant.io/) is the
    central hub.
  * **Dependency Management:** [Renovate](https://github.com/renovatebot/renovate)
    handles dependency updates.

## Architecture

* **Hardware:**
  * **Cluster:** 3x Raspberry Pi 4 (8GB) nodes (`k8s-master-1`,
    `k8s-worker-1`, `k8s-worker-2`).
  * **Network:** UniFi stack (Dream Machine, Switches, APs).
  * **Storage:** Synology DS1621+ NAS (NFS provisioner).
  * **Other:** Raspberry Pi 3b (Pi-hole), various IoT devices (Philips Hue,
    Sonoff, etc.).
* **Network Layout:**
  * `192.168.1.32/28`: Kubernetes cluster.
  * `192.168.1.16/28`: Infrastructure.
  * See `README.md` for full VLAN details.

## Directory Structure

* `ansible/`: Ansible playbooks and inventory for provisioning Raspberry Pis.
  * `hosts.yml`: Inventory file defining `kubernetes` and `piholes` groups.
  * `site.yml`: Main playbook.
* `clusters/home-cluster/`: Kubernetes manifests managed by Flux.
  * `flux-system/`: Flux configuration (GitRepository, Kustomization).
  * `home-assistant/`, `mosquitto/`, `monitoring/`, etc.: Application specific
    manifests.
* `.github/`: GitHub Actions workflows for linting and maintenance.

## Key Workflows

### 1. GitOps Deployment

Changes to the `clusters/home-cluster` directory are automatically deployed by
Flux.

* **Source:** `https://github.com/mfoo/home.git` (branch: `main`).
* **Sync Path:** `./clusters/home-cluster`.
* **Action:** Commit and push changes to `main`. Flux will pick them up within
  1 minute (GitRepository interval) to 10 minutes (Kustomization interval).

### 2. Ansible Configuration

Used for bootstrapping and managing the OS level of the Raspberry Pis.

* **Command:**

  ```bash
  ansible-playbook -i ansible/hosts.yml ansible/site.yml
  ```

* **Linter:** CI runs `ansible-lint ansible/site.yml`.

### 3. Adding a New Kubernetes Node

1. **Provision OS:** Flash generic OS, set hostname, update packages.
2. **Kernel Config:** Add `cgroup_memory=1 cgroup_enable=memory` to
   `/boot/firmware/cmdline.txt`.
3. **Ansible:** Add host to `ansible/hosts.yml` and run the playbook.
4. **Join Cluster:** Use `k3sup` (requires SSH access).

   ```bash
   k3sup join --server-host k8s-master-1 --host <NEW_NODE_HOSTNAME> --user ubuntu
   ```

## Development Conventions

* **Secrets:** Managed via
  [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets).
  **Never commit raw secrets.**
* **Formatting:**
  * Markdown files are linted.
  * Ansible playbooks are linted.
* **CI/CD:** GitHub Actions run linting checks on push and PR.
