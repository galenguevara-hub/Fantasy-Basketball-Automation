import { useCallback, useEffect, useState } from "react";
export function useAsyncData(loader, deps) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [reloadCounter, setReloadCounter] = useState(0);
    const reload = useCallback(() => {
        setReloadCounter((value) => value + 1);
    }, []);
    useEffect(() => {
        const controller = new AbortController();
        setLoading(true);
        setError(null);
        loader(controller.signal)
            .then((payload) => {
            setData(payload);
        })
            .catch((err) => {
            if (err instanceof DOMException && err.name === "AbortError") {
                return;
            }
            const message = err instanceof Error ? err.message : "Unexpected error";
            setError(message);
        })
            .finally(() => {
            setLoading(false);
        });
        return () => controller.abort();
    }, [...deps, loader, reloadCounter]);
    return { data, loading, error, reload };
}
