// SpecImporter.cs
//
// Reads spec/teahouse.room.json (the portable room descriptor used by every
// runtime in this repo) and instantiates VRChat-specific game objects in the
// open scene: spawn points on the VRC_SceneDescriptor, VRC_Station for each
// sit point, and Rigidbody+VRC_Pickup for each interactable pickup.
//
// Re-runnable: subsequent runs delete previously-imported objects (tagged with
// the marker component below) before recreating them.
//
// Place this file at runtimes/vrchat-unity/Editor/SpecImporter.cs inside your
// Unity project. Open via Tools > TeaHouse > Import Spec.

#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace TeaHouse
{
    public class SpecImportedMarker : MonoBehaviour { }

    [Serializable]
    public class Vec3Json { public float[] values; }

    [Serializable]
    public class SpawnPointJson
    {
        public string id;
        public float[] position;
        public float rotationY;
        public int priority;
    }

    [Serializable]
    public class SitPointJson
    {
        public string id;
        public float[] position;
        public float rotationY;
        public string kind;
    }

    [Serializable]
    public class InteractableJson
    {
        public string id;
        public float[] position;
        public float rotationY;
        public string kind;
        public string @event;
    }

    [Serializable]
    public class RoomSpecJson
    {
        public string id;
        public string name;
        public SpawnPointJson[] spawnPoints;
        public SitPointJson[] sitPoints;
        public InteractableJson[] interactables;
    }

    public static class SpecImporter
    {
        private const string DefaultSpecRelativePath =
            "../../../../spec/teahouse.room.json";

        [MenuItem("Tools/TeaHouse/Import Spec")]
        public static void Import()
        {
            string specPath = ResolveSpecPath();
            if (!File.Exists(specPath))
            {
                EditorUtility.DisplayDialog(
                    "TeaHouse",
                    "Could not find spec at:\n" + specPath +
                    "\n\nMake sure spec/teahouse.room.json exists in the repo root.",
                    "OK");
                return;
            }

            string json = File.ReadAllText(specPath);
            var spec = JsonUtility.FromJson<RoomSpecJson>(json);

            ClearPreviousImport();

            var root = new GameObject("TeaHouse_Spec");
            root.AddComponent<SpecImportedMarker>();

            ImportSpawnPoints(root, spec);
            ImportSitPoints(root, spec);
            ImportInteractables(root, spec);

            EditorUtility.DisplayDialog(
                "TeaHouse",
                "Imported " + (spec.spawnPoints?.Length ?? 0) + " spawn points, " +
                (spec.sitPoints?.Length ?? 0) + " sit points, " +
                (spec.interactables?.Length ?? 0) + " interactables.",
                "OK");
        }

        private static string ResolveSpecPath()
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            return Path.GetFullPath(Path.Combine(projectRoot, DefaultSpecRelativePath));
        }

        private static void ClearPreviousImport()
        {
            var existing = UnityEngine.Object.FindObjectsOfType<SpecImportedMarker>();
            foreach (var m in existing)
            {
                UnityEngine.Object.DestroyImmediate(m.gameObject);
            }
        }

        private static Vector3 ToVec3(float[] arr)
        {
            if (arr == null || arr.Length < 3) return Vector3.zero;
            return new Vector3(arr[0], arr[1], arr[2]);
        }

        private static void ImportSpawnPoints(GameObject root, RoomSpecJson spec)
        {
            if (spec.spawnPoints == null) return;
            var parent = new GameObject("Spawn Points");
            parent.transform.SetParent(root.transform);

            foreach (var sp in spec.spawnPoints)
            {
                var go = new GameObject("spawn_" + sp.id);
                go.transform.SetParent(parent.transform);
                go.transform.position = ToVec3(sp.position);
                go.transform.rotation = Quaternion.Euler(0, sp.rotationY, 0);
                // Friend-script TODO: register go.transform on VRC_SceneDescriptor.spawns
            }
        }

        private static void ImportSitPoints(GameObject root, RoomSpecJson spec)
        {
            if (spec.sitPoints == null) return;
            var parent = new GameObject("Sit Points");
            parent.transform.SetParent(root.transform);

            foreach (var s in spec.sitPoints)
            {
                var go = new GameObject("sit_" + s.id);
                go.transform.SetParent(parent.transform);
                go.transform.position = ToVec3(s.position);
                go.transform.rotation = Quaternion.Euler(0, s.rotationY, 0);
                // Friend-script TODO: AddComponent<VRC.SDK3.Components.VRCStation>() and
                // wire stationEnterPlayerLocation / stationExitPlayerLocation to a child Empty.
            }
        }

        private static void ImportInteractables(GameObject root, RoomSpecJson spec)
        {
            if (spec.interactables == null) return;
            var parent = new GameObject("Interactables");
            parent.transform.SetParent(root.transform);

            foreach (var it in spec.interactables)
            {
                var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
                go.name = "interactable_" + it.id;
                go.transform.SetParent(parent.transform);
                go.transform.position = ToVec3(it.position);
                go.transform.rotation = Quaternion.Euler(0, it.rotationY, 0);
                go.transform.localScale = new Vector3(0.1f, 0.1f, 0.1f);
                if (it.kind == "pickup")
                {
                    var rb = go.AddComponent<Rigidbody>();
                    rb.mass = 0.2f;
                    // Friend-script TODO: AddComponent<VRC.SDK3.Components.VRCPickup>()
                }
            }
        }
    }
}
#endif
