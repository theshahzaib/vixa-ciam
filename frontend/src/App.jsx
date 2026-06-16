import { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import SignIn from "./pages/SignIn.jsx";
import RegisterWizard from "./pages/RegisterWizard.jsx";
import ProductsHome from "./pages/ProductsHome.jsx";
import AdminConsole from "./pages/AdminConsole.jsx";

function Shell() {
  const { session } = useAuth();
  const [view, setView] = useState("signin"); // signin | register | home | admin

  // First visit, not logged in → the front door (sign in / create account).
  if (!session) {
    return (
      <div className="app">
        <Brand />
        {view === "register"
          ? <RegisterWizard goSignIn={() => setView("signin")} onDone={() => setView("signin")} />
          : <SignIn onSignedIn={() => setView("home")} goRegister={() => setView("register")} />}
      </div>
    );
  }

  // After sign-in → entitlement-gated surfaces.
  return (
    <div className="app wide">
      <Brand />
      {view === "admin"
        ? <AdminConsole goHome={() => setView("home")} />
        : <ProductsHome goAdmin={() => setView("admin")} />}
    </div>
  );
}

function Brand() {
  return (
    <div className="brand">
      <span className="logo">ViXa</span>
      <span className="tag">Customer Identity &amp; Access Management</span>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
