import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDemoQuery } from "@/query";
import { useCreateDemo } from "@/query/demo";
import { createFileRoute } from "@tanstack/react-router";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { createDemoSchema } from "@/schema/demo";

export const Route = createFileRoute("/_auth/demo")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <div>
      <QueryDemo />
      <PostDemo />
    </div>
  );
}

function QueryDemo() {
  const { isPending, data } = useDemoQuery();
  return <div>{isPending ? "Loading..." : JSON.stringify(data?.data)}</div>;
}

function PostDemo() {
  const { mutate, isPending } = useCreateDemo();
  const { control, handleSubmit } = useForm({
    defaultValues: {
      name: "",
      age: 0,
    },
    resolver: zodResolver(createDemoSchema),
  });
  return (
    <div>
      <h2>Post Demo</h2>
      <form onSubmit={handleSubmit((data) => mutate(data))}>
        <Controller
          control={control}
          name="name"
          render={({ field }) => (
            <div>
              <span>Name:</span>
              <Input {...field} />
            </div>
          )}
        />
        <Controller
          control={control}
          name="age"
          render={({ field }) => (
            <>
              <span>Age:</span>
              <Input {...field} type="number" />
            </>
          )}
        />
        <Button type="submit" disabled={isPending}>
          {isPending ? "Submitting..." : "submit"}
        </Button>
      </form>
    </div>
  );
}
