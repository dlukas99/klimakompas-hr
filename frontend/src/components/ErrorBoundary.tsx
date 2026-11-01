import { Component, type ReactNode } from "react";

interface Props {
  message: string;
  children: ReactNode;
}

/** Keeps a failing part of the page, such as a map without WebGL, from blanking the whole page. */
export class ErrorBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <p
          role="alert"
          className="absolute inset-x-4 top-20 z-10 rounded bg-amber-100 p-3 text-amber-950"
        >
          {this.props.message}
        </p>
      );
    }
    return this.props.children;
  }
}
