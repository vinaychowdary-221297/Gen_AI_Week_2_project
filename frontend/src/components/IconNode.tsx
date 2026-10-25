import { memo, type CSSProperties, type ComponentType } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  Brain,
  Calculator,
  Database,
  FileCheck2,
  FileText,
  Files,
  Folder,
  FolderSearch,
  GitCompareArrows,
  GitMerge,
  Globe,
  Hexagon,
  LogOut,
  Merge,
  Search,
  ShieldCheck,
  Sparkles,
  Tags,
  User,
  UserCheck,
} from "lucide-react";
import type { WorkflowNodeData } from "../lib/workflowLayout";

const ICONS: Record<string, ComponentType<{ className?: string; style?: CSSProperties }>> = {
  user: User,
  "file-text": FileText,
  brain: Brain,
  sparkles: Sparkles,
  search: Search,
  database: Database,
  "git-merge": GitMerge,
  "git-compare": GitCompareArrows,
  vector: Hexagon,
  pinecone: Hexagon,
  merge: Merge,
  "shield-check": ShieldCheck,
  calculator: Calculator,
  "folder-search": FolderSearch,
  folder: Folder,
  files: Files,
  "file-check": FileCheck2,
  "user-check": UserCheck,
  globe: Globe,
  tags: Tags,
  output: LogOut,
};

const statusBg: Record<string, string> = {
  idle: "transparent",
  running: "rgba(56, 189, 248, 0.28)",
  completed: "rgba(34, 197, 94, 0.28)",
  failed: "rgba(239, 68, 68, 0.28)",
  skipped: "transparent",
};

const statusGlow: Record<string, string> = {
  idle: "opacity-80",
  running: "animate-pulse",
  completed: "",
  failed: "",
  skipped: "opacity-35",
};

function IconNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as WorkflowNodeData;
  const Icon = ICONS[nodeData.icon] || Hexagon;
  const glow = statusGlow[nodeData.status] || statusGlow.idle;
  const bg = statusBg[nodeData.status] || statusBg.idle;
  const scale = nodeData.scale ?? 1;
  const iconPx = Math.round(56 * scale);
  const widthPx = Math.round(130 * scale);
  const fontPx = Math.max(11, Math.round(13 * scale));

  return (
    <div
      className={`relative flex flex-col items-center gap-2 ${selected ? "scale-105" : ""}`}
      style={{ width: widthPx }}
      title={`${nodeData.label} — ${nodeData.status}`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!-left-1 !h-2.5 !w-2.5 !border-0 !bg-accent-cyan"
      />

      <div
        className="relative overflow-hidden rounded-md transition-colors duration-300"
        style={{
          width: iconPx,
          height: iconPx,
          backgroundColor: bg,
        }}
      >
        <Icon
          className={`h-full w-full ${glow}`}
          style={{
            color: nodeData.accent,
            strokeWidth: 1.75,
            width: iconPx,
            height: iconPx,
          }}
        />
      </div>

      <div className="text-center">
        <div
          className="font-display font-semibold leading-tight text-slate-100"
          style={{ fontSize: fontPx }}
        >
          {nodeData.label}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!-right-1 !h-2.5 !w-2.5 !border-0 !bg-accent-violet"
      />
    </div>
  );
}

export default memo(IconNodeComponent);
