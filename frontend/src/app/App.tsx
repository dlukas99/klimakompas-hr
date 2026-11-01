import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router";
import { Layout } from "../components/Layout";
import hr from "../i18n/hr.json";
import { AboutPage } from "../pages/AboutPage";
import { AssistantPage } from "../pages/AssistantPage";
import { DataPage } from "../pages/DataPage";
import { HomePage } from "../pages/HomePage";
import { JlsListPage } from "../pages/JlsListPage";

// The map and chart libraries are large, so only the pages that use them load them.
const MapPage = lazy(() =>
  import("../pages/MapPage").then((module) => ({ default: module.MapPage })),
);
const JlsPage = lazy(() =>
  import("../pages/JlsPage").then((module) => ({ default: module.JlsPage })),
);
const CardPage = lazy(() =>
  import("../pages/CardPage").then((module) => ({ default: module.CardPage })),
);

const queryClient = new QueryClient();

function NotFound() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <h1 className="text-2xl font-bold">{hr.app.notFound}</h1>
      <Link to="/" className="mt-2 inline-block underline">
        {hr.app.backHome}
      </Link>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense
          fallback={
            <p role="status" className="p-4">
              {hr.app.loading}
            </p>
          }
        >
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<HomePage />} />
              <Route path="karta" element={<MapPage />} />
              <Route path="iskaznica" element={<CardPage />} />
              <Route path="opcine" element={<JlsListPage />} />
              <Route path="opcine/:code" element={<JlsPage />} />
              <Route path="asistent" element={<AssistantPage />} />
              <Route path="podaci" element={<DataPage />} />
              <Route path="o-projektu" element={<AboutPage />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
