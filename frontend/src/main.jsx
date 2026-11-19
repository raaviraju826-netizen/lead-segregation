import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { SourceProvider } from "./context/SourceContext";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import UploadPage from "./pages/UploadPage";
import IndustryPage from "./pages/IndustryPage";
import AllLeads from "./pages/AllLeads";
import ReviewQueue from "./pages/ReviewQueue";
import DuplicatesPage from "./pages/DuplicatesPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import SettingsPage from "./pages/SettingsPage";
import LeadDetail from "./pages/LeadDetail";
import GmailPage from "./pages/GmailPage";
import ExportPage from "./pages/ExportPage";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <SourceProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="industry/:slug" element={<IndustryPage />} />
            <Route path="leads" element={<AllLeads />} />
            <Route path="leads/:id" element={<LeadDetail />} />
            <Route path="review" element={<ReviewQueue />} />
            <Route path="duplicates" element={<DuplicatesPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="gmail" element={<GmailPage />} />
            <Route path="export" element={<ExportPage />} />
            <Route path="*" element={<div className="py-20 text-center text-slate-500">Page not found</div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </SourceProvider>
  </React.StrictMode>
);
