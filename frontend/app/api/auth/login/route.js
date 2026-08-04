import { NextResponse } from "next/server";

const COOKIE_NAME = "chairtime_token";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

export async function POST(request) {
    try {
        const apiUrl = process.env.CHAIRTIME_API_URL;

        if (!apiUrl) {
            return NextResponse.json(
                { error: "Backend URL is not configured." },
                { status: 500 }
            );
        }

        const body = await request.json();

        const response = await fetch(`${apiUrl}/api/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
            cache: "no-store",
        });

        const data = await response.json();

        if (!response.ok) {
            return NextResponse.json(data, {
                status: response.status,
            });
        }

        const token =
            data.access_token ||
            data.accessToken ||
            data.token;

        if (!token) {
            return NextResponse.json(
                { error: "No access token returned." },
                { status: 500 }
            );
        }

        const result = NextResponse.json({
            success: true,
            user: data.user,
        });

        result.cookies.set({
            name: COOKIE_NAME,
            value: token,
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: "lax",
            path: "/",
            maxAge: COOKIE_MAX_AGE_SECONDS,
        });

        return result;
    } catch (err) {
        console.error(err);

        return NextResponse.json(
            { error: "Unable to contact authentication server." },
            { status: 500 }
        );
    }
}