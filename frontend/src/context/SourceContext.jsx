import { createContext, useContext, useState } from "react";

const Ctx = createContext(null);

/** Global data-source switch. "gmail" = rajurajuu970@gmail.com inbox; "upload" = uploaded files; "demo" = synthetic benchmark. */
export function SourceProvider({ children }) {
  const [source, setSourceState] = useState(localStorage.getItem("leadsense_source") || "gmail");
  const setSource = (s) => {
    localStorage.setItem("leadsense_source", s);
    setSourceState(s);
  };
  return <Ctx.Provider value={{ source, setSource }}>{children}</Ctx.Provider>;
}

export const useSource = () => useContext(Ctx);
