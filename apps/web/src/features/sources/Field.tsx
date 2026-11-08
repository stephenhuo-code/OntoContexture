import { useId } from "react";

/** 表单字段：标签经 htmlFor 关联控件，帮助文字经 aria-describedby 关联，不并入可访问名称 */
export function Field({
  label,
  help,
  full,
  children,
}: {
  label: string;
  help?: string;
  full?: boolean;
  children: (props: {
    id: string;
    "aria-describedby"?: string;
  }) => React.ReactNode;
}) {
  const id = useId();
  return (
    <div className={`field${full ? " full" : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children({ id, "aria-describedby": help ? `${id}-help` : undefined })}
      {help && (
        <small className="help" id={`${id}-help`}>
          {help}
        </small>
      )}
    </div>
  );
}
