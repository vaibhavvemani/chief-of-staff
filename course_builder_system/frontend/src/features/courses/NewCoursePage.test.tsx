import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { courseIdForSubject, NewCoursePage } from "./NewCoursePage";

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}{location.search}</div>;
}

afterEach(() => vi.unstubAllGlobals());

describe("NewCoursePage durable course identity", () => {
  it("matches the backend's generated course ID contract", () => {
    expect(courseIdForSubject("Coffee making for beginners")).toBe(
      "coffee-making-for-beginners-course",
    );
  });

  it("recovers a lost creation response at the exact submitted course ID", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new TypeError("connection lost")));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/courses/new"]}>
          <Routes>
            <Route path="/courses/new" element={<NewCoursePage />} />
            <Route path="*" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.type(
      screen.getByLabelText(/What should this course teach/),
      "Coffee making",
    );
    await user.click(screen.getByRole("button", { name: /Create Brief/ }));

    expect(await screen.findByTestId("location")).toHaveTextContent(
      "/courses/coffee-making-course/brief?preview=1&mode=live",
    );
  });
});
