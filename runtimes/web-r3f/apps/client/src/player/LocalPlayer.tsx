import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { PointerLockControls } from "@react-three/drei";
import {
  CapsuleCollider,
  RigidBody,
  type RapierRigidBody,
} from "@react-three/rapier";
import * as THREE from "three";
import type { RoomSpec, AnimationState } from "@teahouse/shared";
import { useKeyboard } from "./useKeyboard.js";
import { useNetwork } from "../net/networkContext.js";
import { config } from "../config.js";

interface Props {
  spec: RoomSpec;
}

const WALK_SPEED = 2.4;
const SPRINT_MULT = 1.7;
const JUMP_VELOCITY = 4.5;
const PLAYER_HEIGHT = 1.7;
const EYE_HEIGHT = 1.55;

// Reusable scratch vectors so useFrame doesn't allocate every tick.
const fwdVec = new THREE.Vector3();
const rightVec = new THREE.Vector3();
const moveVec = new THREE.Vector3();
const WORLD_UP = new THREE.Vector3(0, 1, 0);

export function LocalPlayer({ spec }: Props) {
  const body = useRef<RapierRigidBody>(null);
  const keys = useKeyboard();
  const { camera } = useThree();
  const network = useNetwork();
  const lastSent = useRef(0);
  const onGround = useRef(false);

  useEffect(() => {
    const spawn = spec.spawnPoints[0];
    if (!body.current) return;
    body.current.setTranslation(
      { x: spawn.position[0], y: spawn.position[1] + PLAYER_HEIGHT / 2, z: spawn.position[2] },
      true,
    );
    // spec rotationY is interpreted as a Three.js Y-axis rotation in degrees.
    // 0 = facing -Z (north / into the building from the entrance).
    camera.rotation.set(0, (spawn.rotationY * Math.PI) / 180, 0);
  }, [spec, camera]);

  useFrame((state, dt) => {
    if (!body.current) return;

    const k = keys.current;

    // Derive horizontal forward/right directly from the camera so movement
    // always tracks where the camera is actually looking, regardless of yaw.
    camera.getWorldDirection(fwdVec);
    fwdVec.y = 0;
    if (fwdVec.lengthSq() < 1e-6) {
      // Camera looking straight up/down — fall back to a default forward.
      fwdVec.set(0, 0, -1);
    } else {
      fwdVec.normalize();
    }
    // right = forward × up, which is the camera's local +X projected to the ground plane.
    rightVec.crossVectors(fwdVec, WORLD_UP).normalize();

    let inputF = 0; // forward / back (W = +1, S = -1)
    let inputR = 0; // right / left  (D = +1, A = -1)
    if (k.forward) inputF += 1;
    if (k.back) inputF -= 1;
    if (k.right) inputR += 1;
    if (k.left) inputR -= 1;

    const len = Math.hypot(inputF, inputR);
    if (len > 0) {
      inputF /= len;
      inputR /= len;
    }

    moveVec
      .copy(fwdVec)
      .multiplyScalar(inputF)
      .addScaledVector(rightVec, inputR);

    const speed = WALK_SPEED * (k.sprint ? SPRINT_MULT : 1);
    const linvel = body.current.linvel();
    body.current.setLinvel(
      {
        x: moveVec.x * speed,
        y: linvel.y,
        z: moveVec.z * speed,
      },
      true,
    );

    if (k.jump && onGround.current) {
      body.current.setLinvel({ x: linvel.x, y: JUMP_VELOCITY, z: linvel.z }, true);
      onGround.current = false;
    }

    const t = body.current.translation();
    camera.position.set(t.x, t.y + EYE_HEIGHT - PLAYER_HEIGHT / 2, t.z);

    onGround.current = Math.abs(linvel.y) < 0.1;

    lastSent.current += dt;
    if (network && lastSent.current >= 1 / config.poseHz) {
      lastSent.current = 0;
      const moving = len > 0;
      const animationState: AnimationState = moving
        ? k.sprint
          ? "running"
          : "walking"
        : "idle";
      network.sendPose({
        position: { x: t.x, y: t.y - PLAYER_HEIGHT / 2, z: t.z },
        rotationY: camera.rotation.y,
        animationState,
      });
    }
  });

  return (
    <>
      <PointerLockControls />
      <RigidBody
        ref={body}
        colliders={false}
        type="dynamic"
        enabledRotations={[false, false, false]}
        mass={70}
        linearDamping={4}
        ccd
      >
        <CapsuleCollider args={[(PLAYER_HEIGHT - 0.6) / 2, 0.3]} />
      </RigidBody>
    </>
  );
}
