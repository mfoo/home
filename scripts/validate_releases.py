import os
import yaml
import subprocess
import sys

def main():
    repo_map = {} # (name, namespace) -> url
    releases = []

    print("🔍 Scanning for HelmRepository and HelmRelease files...")
    # 1. Scan for Repos and Releases
    for root, dirs, files in os.walk("clusters"):
        for file in files:
            if not file.endswith((".yaml", ".yml")):
                continue
            path = os.path.join(root, file)
            with open(path, "r") as f:
                try:
                    docs = yaml.safe_load_all(f)
                    for doc in docs:
                        if not doc: continue
                        kind = doc.get("kind")
                        if kind == "HelmRepository":
                            meta = doc.get("metadata", {})
                            name = meta.get("name")
                            ns = meta.get("namespace", "flux-system")
                            url = doc.get("spec", {}).get("url")
                            if name and url:
                                repo_map[(name, ns)] = url
                        elif kind == "HelmRelease":
                            releases.append((doc, path))
                except Exception as e:
                    print(f"⚠️ Error parsing {path}: {e}")

    # 2. Add Repos
    print(f"📦 Found {len(repo_map)} Helm Repositories. Adding them...")
    for (name, ns), url in repo_map.items():
        # Use a unique name to avoid collisions if same name in diff namespaces?
        # Typically global uniqueness is preferred, or we prefix.
        # But for 'helm repo add', the name is local alias.
        # We will use the name from the yaml.
        try:
            subprocess.run(["helm", "repo", "add", name, url], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to add repo {name} ({url}): {e.stderr.decode()}")
    
    print("🔄 Updating Helm Repos...")
    subprocess.run(["helm", "repo", "update"], check=False) # Don't fail hard if one repo fails

    # 3. Process Releases
    failed = False
    print(f"🚀 Validating {len(releases)} Helm Releases...")
    
    for release, path in releases:
        meta = release.get("metadata", {})
        name = meta.get("name")
        ns = meta.get("namespace", "default")
        spec = release.get("spec", {})
        chart_spec = spec.get("chart", {}).get("spec", {})
        
        chart = chart_spec.get("chart")
        version = chart_spec.get("version")
        source_ref = chart_spec.get("sourceRef", {})
        repo_name = source_ref.get("name")
        repo_ns = source_ref.get("namespace", "flux-system") # Default to flux-system if not spec'd? Or assume same ns?
        # Flux doc: "namespace: Namespace of the referent. Defaults to the HelmRelease namespace."
        # But in this repo structure, most seem to rely on flux-system.
        
        # Heuristic: try finding it in the specified ns (or release ns), then fallback to flux-system
        repo_url = repo_map.get((repo_name, repo_ns))
        if not repo_url and repo_ns != "flux-system":
             repo_url = repo_map.get((repo_name, "flux-system"))
        
        # If still not found, check if we have it by name regardless of namespace (last resort)
        if not repo_url:
            for (r_name, r_ns), r_url in repo_map.items():
                if r_name == repo_name:
                    repo_url = r_url
                    break

        if not repo_url:
            print(f"⚠️  Skipping {name} ({path}): Repo '{repo_name}' not found in scanned repositories.")
            continue

        print(f"▶️  Validating {name} (Chart: {repo_name}/{chart}:{version})...")

        # Template
        # Note: We use repo_name as the alias since we added it as such.
        cmd_template = [
            "helm", "template", name, f"{repo_name}/{chart}",
            "--namespace", ns,
            "--include-crds",
            "-f", "-" 
        ]
        
        if version:
             cmd_template.extend(["--version", version])
        
        values = spec.get("values", {})
        values_yaml = yaml.dump(values)
        
        p_template = subprocess.Popen(
            cmd_template, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = p_template.communicate(input=values_yaml)
        
        if p_template.returncode != 0:
            print(f"❌ Helm Template Failed for {name}:")
            print(stderr)
            failed = True
            continue

        # Run Kubeconform
        # We process the output line by line or as a block.
        # Kubeconform reads from stdin.
        
        cmd_kubeconform = [
            "kubeconform",
            "-summary",
            "-ignore-missing-schemas",
            "-strict",
            "-schema-location", "default",
            "-schema-location", "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json",
            "-"
        ]
        
        p_conf = subprocess.Popen(
            cmd_kubeconform,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = p_conf.communicate(input=stdout)
        
        if p_conf.returncode != 0:
            print(f"❌ Kubeconform Failed for {name}:")
            print(out)
            print(err)
            failed = True
        else:
            # Check output for "Invalid" count manually if needed, or rely on exit code (kubeconform exits 1 if invalid)
            # Kubeconform output goes to stdout.
            if "Invalid: 0" not in out and "Invalid: " in out:
                 print(f"❌ Validation Errors for {name}:")
                 print(out)
                 failed = True
            else:
                 print(f"✅ {name} Validated.")

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
