import { useId } from "react";

import type { Locale } from "../../shared/copy";
import { DokkaebiSticker } from "./DokkaebiSticker";
import { dokkaebiExpressions, type DokkaebiExpression } from "./dokkaebiCatalog";

type DokkaebiPickerProps = {
  expression: DokkaebiExpression;
  onChange: (expression: DokkaebiExpression) => void;
  locale: Locale;
};

export function DokkaebiPicker({ expression, onChange, locale }: DokkaebiPickerProps) {
  const groupId = useId();

  return (
    <fieldset className="dokkaebi-picker">
      <legend>{locale === "ko" ? "마음에 드는 표정을 골라 주세요" : "Choose your expression"}</legend>
      <div className="dokkaebi-picker-grid">
        {dokkaebiExpressions.map((item) => (
          <label
            className={`dokkaebi-option${expression === item.id ? " is-selected" : ""}`}
            key={item.id}
          >
            <input
              type="radio"
              name={groupId}
              value={item.id}
              checked={expression === item.id}
              onChange={() => onChange(item.id)}
            />
            <DokkaebiSticker expression={item.id} size={88} decorative loading="lazy" />
            <span>{item.label[locale]}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
