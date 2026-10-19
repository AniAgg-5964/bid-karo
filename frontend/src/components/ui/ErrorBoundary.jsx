import { Component } from "react";
import { TriangleAlert } from "lucide-react";

import { Button } from "./Button";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // Keep the console useful without leaking user data into a remote service.
    console.error("BidKaro UI error", error, info?.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-mist px-4 dark:bg-navy-950">
          <div className="surface max-w-md p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-red-50 text-red-600 dark:bg-red-950 dark:text-red-300">
              <TriangleAlert className="h-6 w-6" />
            </div>
            <h1 className="mt-4 text-lg font-semibold text-navy-900 dark:text-white">Something went wrong</h1>
            <p className="mt-2 text-sm muted">
              The page could not be rendered. Your stored data has not been changed.
            </p>
            <Button className="mt-6" onClick={() => window.location.reload()}>
              Reload page
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
