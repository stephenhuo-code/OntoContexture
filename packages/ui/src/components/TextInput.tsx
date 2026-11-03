import { forwardRef, useId, type InputHTMLAttributes } from "react";

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}
export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  function TextInput({ label, id, className = "", ...props }, ref) {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    return (
      <div className="ctx-field">
        <label htmlFor={inputId}>{label}</label>
        <input
          {...props}
          ref={ref}
          id={inputId}
          className={`ctx-input ${className}`}
        />
      </div>
    );
  },
);
