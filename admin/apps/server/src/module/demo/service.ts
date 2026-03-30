export function queryDemo() {
  return {
    msg: "Demo data retrieved successfully",
    data: {
      name: "demo",
      age: 18,
    },
  };
}

export function createDemo(data: { name: string; age: number }) {
  return {
    msg: "Demo created successfully",
    data,
  };
}
