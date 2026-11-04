import { createBrowserRouter, type RouteObject } from "react-router";

import { RootLayout, NotFoundComponent, ErrorComponent } from "./RootLayout";
import Index from "./pages/Index";
import AppShell from "./pages/AppShell";
import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <RootLayout />,
    errorElement: <ErrorComponent />,
    children: [
      { index: true, element: <Index /> },
      { path: "app", element: <AppShell /> },
      { path: "signin", element: <SignIn /> },
      { path: "signup", element: <SignUp /> },
      { path: "*", element: <NotFoundComponent /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
