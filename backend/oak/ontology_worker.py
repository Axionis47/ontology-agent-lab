"""Check one generated OWL file. Return a report without inferred graph facts."""

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


def verify_file(path, heap_mb):
    result = {
        "status": "infrastructure_error",
        "versions": {},
        "errors": [],
        "unsatisfiable_classes": [],
    }
    try:
        import owlready2 as owl
        import owlready2.reasoning as reasoning
    except ImportError:
        result["errors"] = [
            {"code": "missing_owlready2", "message": "Install the pinned Owlready2 dependency."}
        ]
        return result
    result["versions"]["owlready2"] = importlib.metadata.version("owlready2")
    jar = Path(owl.__file__).parent / "hermit" / "HermiT.jar"
    try:
        result["versions"]["hermit_jar_sha256"] = hashlib.sha256(jar.read_bytes()).hexdigest()
        with ZipFile(jar) as archive:
            manifest = archive.read("META-INF/MANIFEST.MF").decode()
        result["versions"]["hermit"] = next(
            line.split(":", 1)[1].strip()
            for line in manifest.splitlines()
            if line.startswith("Implementation-Version:")
        )
    except (OSError, KeyError, StopIteration):
        result["errors"] = [
            {"code": "missing_hermit", "message": "The bundled HermiT package is incomplete."}
        ]
        return result
    java = os.environ.get("OAK_JAVA") or "java"
    try:
        version = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=5)
        if version.returncode:
            raise OSError("Java could not start.")
        result["versions"]["java"] = (version.stderr or version.stdout).splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        result["errors"] = [
            {
                "code": "missing_java",
                "message": "Configure a working Java runtime with OAK_JAVA or PATH.",
            }
        ]
        return result
    owl.JAVA_EXE = java
    reasoning.JAVA_MEMORY = heap_mb
    world = owl.World()
    try:
        ontology = world.get_ontology(Path(path).resolve().as_uri()).load()
        owl.sync_reasoner_hermit(world, debug=0, infer_property_values=False)
        result["unsatisfiable_classes"] = sorted(
            item.iri for item in world.inconsistent_classes() if item is not owl.Nothing
        )
        result["status"] = "invalid" if result["unsatisfiable_classes"] else "passed"
        if result["unsatisfiable_classes"]:
            result["errors"] = [
                {
                    "code": "unsatisfiable_classes",
                    "message": "Declared entity classes cannot have instances.",
                }
            ]
        # Keep the loaded ontology alive until the reasoner and class check finish.
        del ontology
    except owl.OwlReadyInconsistentOntologyError:
        result.update(
            status="invalid",
            errors=[
                {
                    "code": "inconsistent_ontology",
                    "message": "The generated ontology is inconsistent.",
                }
            ],
        )
    except owl.OwlReadyJavaError:
        result["errors"] = [
            {"code": "reasoner_failure", "message": "HermiT could not complete verification."}
        ]
    except Exception as error:
        result["errors"] = [
            {
                "code": "worker_failure",
                "message": f"The ontology worker failed ({type(error).__name__}).",
            }
        ]
    finally:
        world.close()
    return result


if __name__ == "__main__":
    try:
        output = verify_file(sys.argv[1], int(sys.argv[2]))
    except Exception as error:
        output = {
            "status": "infrastructure_error",
            "versions": {},
            "errors": [
                {
                    "code": "worker_failure",
                    "message": f"The worker could not start ({type(error).__name__}).",
                }
            ],
            "unsatisfiable_classes": [],
        }
    print(json.dumps(output, sort_keys=True))
