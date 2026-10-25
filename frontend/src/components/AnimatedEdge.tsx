import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";

type EdgeData = {
  active?: boolean;
  traversed?: boolean;
  feedback?: boolean;
};

export default function AnimatedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: 0.35,
  });

  const d = (data || {}) as EdgeData;
  const active = Boolean(d.active);
  const traversed = Boolean(d.traversed) && !active;
  const feedback = Boolean(d.feedback);

  // Idle paths stay readable on the dark canvas; active/traversed are brighter
  let stroke = "#cbd5e1";
  let strokeWidth = 2.25;
  let opacity = 0.95;

  if (active) {
    stroke = feedback ? "#c4b5fd" : "#22d3ee";
    strokeWidth = 3;
    opacity = 1;
  } else if (traversed) {
    stroke = feedback ? "#a78bfa" : "#38bdf8";
    strokeWidth = 2.4;
    opacity = 0.95;
  }

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{ stroke, strokeWidth, opacity }}
      />
      {/* Particles only while this specific path segment is executing */}
      {active && (
        <>
          <path
            d={edgePath}
            fill="none"
            stroke={feedback ? "#c4b5fd" : "#67e8f9"}
            strokeWidth={2}
            className="edge-flow"
            style={{ filter: "drop-shadow(0 0 4px rgba(34,211,238,0.8))" }}
          />
          <circle r="3.5" fill="#fff">
            <animateMotion dur="1.2s" repeatCount="indefinite" path={edgePath} />
          </circle>
        </>
      )}
    </>
  );
}
