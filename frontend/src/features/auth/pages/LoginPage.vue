<script setup lang="ts">
import { ref } from 'vue';

const email = ref("");

function handleLogin() {
  if (!email.value) {
    alert("Please enter your email.");
    return;
  }

  console.log("Logging in with email:", email.value);
  // Add your login logic here
}

</script>

<template>
  <div class="flex h-screen items-center justify-center bg-gray-100">
    <div class="w-full max-w-sm rounded-2xl bg-white p-6 shadow-md">
      <h1 class="mb-4 text-xl font-bold">Login</h1>
      <form @submit.prevent="handleLogin" class="flex flex-col space-y-4">
        <label class="flex flex-col text-sm font-medium">
          Email:
          <input
            v-model="email"
            type="email"
            placeholder="you@example.com"
            class="mt-1 rounded border p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </label>
        <button
          type="submit"
          class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        >
          Login
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>

</style>
