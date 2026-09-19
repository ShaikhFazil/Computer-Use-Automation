import { Routes, Route, useSearchParams, Navigate } from "react-router-dom";
import Shell from "./components/Shell.jsx";
import Lookup from "./pages/Lookup.jsx";
import MemberDetail from "./pages/MemberDetail.jsx";
import NewSubAccount from "./pages/NewSubAccount.jsx";
import Confirm from "./pages/Confirm.jsx";
import TransferNew from "./pages/TransferNew.jsx";
import TransferConfirm from "./pages/TransferConfirm.jsx";
import SessionExpired from "./pages/SessionExpired.jsx";
import Placeholder from "./pages/Placeholder.jsx";


function SessionGate({ children }) {
  const [params] = useSearchParams();
  if (params.get("session") === "expired") return <SessionExpired />;
  return children;
}

export default function App() {
  return (
    <Shell>
      <SessionGate>
        <Routes>
          <Route path="/" element={<Lookup />} />
          <Route path="/member/:id" element={<MemberDetail />} />
          <Route path="/member/:id/sub-account/new" element={<NewSubAccount />} />
          <Route path="/member/:id/sub-account/confirm" element={<Confirm />} />
          <Route path="/member/:id/transfer/new" element={<TransferNew />} />
          <Route path="/member/:id/transfer/confirm" element={<TransferConfirm />} />
          <Route path="/accounts" element={<Placeholder title="Accounts" />} />
          <Route path="/transactions" element={<Placeholder title="Transactions" />} />
          <Route path="/settings" element={<Placeholder title="Settings" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </SessionGate>
    </Shell>
  );
}
