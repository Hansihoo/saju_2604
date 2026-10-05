import { useEffect, useState } from "react";

import { dokkaebiMoods, isDokkaebiExpression, type DokkaebiExpression } from "./dokkaebiCatalog";

const storageKey = "saju.dokkaebi.expression.v1";

function readPreference(): DokkaebiExpression {
  try {
    const value = window.localStorage.getItem(storageKey);
    return isDokkaebiExpression(value) ? value : dokkaebiMoods.reading;
  } catch {
    return dokkaebiMoods.reading;
  }
}

export function useDokkaebiPreference() {
  const [expression, setExpression] = useState<DokkaebiExpression>(readPreference);

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, expression);
    } catch {
      // Private browsing or disabled storage must not prevent sticker selection.
    }
  }, [expression]);

  useEffect(() => {
    function syncPreference(event: StorageEvent) {
      if (event.key === storageKey || event.key === null) {
        setExpression(readPreference());
      }
    }
    window.addEventListener("storage", syncPreference);
    return () => window.removeEventListener("storage", syncPreference);
  }, []);

  return { expression, setExpression };
}
